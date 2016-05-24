#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import mimetypes
import json
import uuid
from PIL import Image
import time
import traceback
import sys
import re
from bs4 import BeautifulSoup
import requests

# library for working with LOC BagIt standard 
import bagit

# celery
from WSUDOR_Manager import celery

# eulfedora
import eulfedora
from eulfedora.models import  Relation, ReverseRelation, FileDatastream, XmlDatastream, DatastreamObject, DigitalObject

# WSUDOR
import WSUDOR_ContentTypes
from WSUDOR_Manager.solrHandles import solr_handle, solr_bookreader_handle
from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager import redisHandles, helpers, utilities
from WSUDOR_API.functions.packagedFunctions import singleObjectPackage

# localconfig
import localConfig

# import manifest factory instance
from inc.manifest_factory import iiif_manifest_factory_instance

# derivatives
from inc.derivatives import JP2DerivativeMaker


####################################################################################
# From Readux
####################################################################################


# class WSUDOR_Readux_VirtualBook(DigitalObject):

# 	'''Fedora Book Object.  Extends :class:`~eulfedora.models.DigitalObject`.

# 	.. Note::

# 		This is a bare-minimum model, only implemented enough to support
# 		indexing and access to volumes.
# 	'''
# 	#: content model for books
# 	BOOK_CONTENT_MODEL = 'info:fedora/emory-control:ScannedBook-1.0'
# 	CONTENT_MODELS = [BOOK_CONTENT_MODEL]

# 	#: marcxml :class:`~eulfedora.models.XMlDatastream` with the metadata
# 	#: record for all associated volumes; xml content will be instance of
# 	#: :class:`MinMarcxml`
# 	marcxml = XmlDatastream("MARCXML", "MARC21 metadata", MinMarcxml, defaults={
# 		'control_group': 'M',
# 		'versionable': True,
# 	})

# 	#: :class:`~readux.collection.models.Collection` this book belongs to,
# 	#: via fedora rels-ext isMemberOfcollection
# 	collection = Relation(relsext.isMemberOfCollection, type=Collection)

# 	#: default view for new object
# 	NEW_OBJECT_VIEW = 'books:volume'
# 	# NOTE: this is semi-bogus, since book-level records are currently
# 	# not displayed in readux

# 	@permalink
# 	def get_absolute_url(self):
# 		'Absolute url to view this object within the site'
# 		return (self.NEW_OBJECT_VIEW, [str(self.pid)])

# 	@property
# 	def best_description(self):
# 		'''Single best description to use when only one can be displayed (e.g.,
# 		for twitter or facebook integration). Currently selects the longest
# 		description from available dc:description values.
# 		'''
# 		# for now, just return the longest description
# 		# eventually we should be able to update this to make use of the MARCXML
# 		descriptions = list(self.dc.content.description_list)
# 		if descriptions:
# 			return sorted(descriptions, key=len, reverse=True)[0]

# 	@staticmethod
# 	def pids_by_label(label):
# 		'''Search Books by label and return a list of matching pids.'''
# 		solr = solr_interface()
# 		q = solr.query(content_model=Book.BOOK_CONTENT_MODEL,
# 					   label=label).field_limit('pid')
# 		return [result['pid'] for result in q]


# # # Virtual Readux Volume Object
# class WSUDOR_Readux_VirtualVolume(object):



####################################################################################
# Local
####################################################################################

# Virtual Readux Book Object
class WSUDOR_Readux_VirtualBook(DigitalObject):

	target_datastreams = {
		"DC" : {
			"mimetype":"text/xml",
			"label":"Dublin Core"
		},
		"MARCXML" : {
			"mimetype":"text/xml",
			"label":"MARC21 XML"
		},
		"RELS-EXT" : {
			"mimetype":"application/rdf+xml",
			"label":"RELS-EXT"
		}
	}

	def create(self, wsudor_book):
		
		'''
		Create Readux virtual Book object based on WSUDOR_WSUebook
		'''

		# PID
		pid_prefix = wsudor_book.pid
		self.pid = pid_prefix + "_Readux_VirtualBook"

		# init
		print "Initializing %s" % (self.pid)
		self.save()

		# Dublin Core
		self.dc = wsudor_book.ohandle.dc.content.serialize()

		# write POLICY datastream
		# NOTE: 'E' management type required, not 'R'
		print "Using policy:",wsudor_book.objMeta['policy']
		policy_suffix = wsudor_book.objMeta['policy'].split("info:fedora/")[1]
		policy_handle = eulfedora.models.DatastreamObject(self,"POLICY", "POLICY", mimetype="text/xml", control_group="E")
		policy_handle.ds_location = "http://localhost/fedora/objects/%s/datastreams/POLICY_XML/content" % (policy_suffix)
		policy_handle.label = "POLICY"
		policy_handle.save()

		# label
		self.label = wsudor_book.ohandle.label

		# Build RELS-EXT
		object_relationships = [

			# Readux specific
			{
				"predicate": "info:fedora/fedora-system:def/model#hasModel",
				"object": "info:fedora/emory-control:ScannedBook-1.0"
			},
			{
				"predicate": "info:fedora/fedora-system:def/relations-external#isMemberOfCollection",
				"object": "info:fedora/wayne:collectionWSUebooks"
			},
			{
				"predicate": "info:fedora/fedora-system:def/relations-external#hasConstituent",
				"object": "info:fedora/%s_Readux_VirtualVolume" % (pid_prefix)
			},
			
			# WSUDOR related
			{
				"predicate": "http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isVirtual",
				"object": "True"
			},
			{
				"predicate": "http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isVirtualFor",
				"object": "info:fedora/%s" % wsudor_book.pid
			},
			{
				"predicate": "http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/hasSecurityPolicy",
				"object": "info:fedora/wayne:WSUDORSecurity-permit-apia-unrestricted"
			}
		]

		# write explicit RELS-EXT relationships			
		for relationship in object_relationships:
			print "Writing relationship:",str(relationship['predicate']),str(relationship['object'])
			self.add_relationship(str(relationship['predicate']),str(relationship['object']))


		# Content Type Unique
		###############################################################

		# MARCXML
		MARCXML_handle = eulfedora.models.DatastreamObject(self,"MARCXML", "MARCXML", mimetype="text/xml", control_group="M")
		MARCXML_handle.content = "</empty>"
		MARCXML_handle.label = "MARCXML"
		MARCXML_handle.save()

		###############################################################

		# save new object
		self.save()



# Virtual Readux Volume Object
class WSUDOR_Readux_VirtualVolume(DigitalObject):

	target_datastreams = {
		"DC" : {
			"mimetype":"text/xml",
			"label":"Dublin Core"
		},
		"OCR" : {
			"mimetype":"text/xml",
			"label":"OCR from Abbyy"
		},
		"PDF" : {
			"mimetype":"application/pdf",
			"label":"Full-text PDF"
		},
		"RELS-EXT" : {
			"mimetype":"application/rdf+xml",
			"label":"RELS-EXT"
		}
	}

	def create(self, wsudor_book):
		
		'''
		Create Readux virtual Volume object based on WSUDOR_WSUebook
		'''

		# PID
		pid_prefix = wsudor_book.pid
		self.pid = pid_prefix + "_Readux_VirtualVolume"

		# init
		print "Initializing %s" % (self.pid)
		self.save()

		# Dublin Core
		self.dc = wsudor_book.ohandle.dc.content.serialize()

		# write POLICY datastream
		# NOTE: 'E' management type required, not 'R'
		print "Using policy:",wsudor_book.objMeta['policy']
		policy_suffix = wsudor_book.objMeta['policy'].split("info:fedora/")[1]
		policy_handle = eulfedora.models.DatastreamObject(self,"POLICY", "POLICY", mimetype="text/xml", control_group="E")
		policy_handle.ds_location = "http://localhost/fedora/objects/%s/datastreams/POLICY_XML/content" % (policy_suffix)
		policy_handle.label = "POLICY"
		policy_handle.save()

		# label
		self.label = wsudor_book.ohandle.label

		# Build RELS-EXT
		object_relationships = [

			# Readux specific
			{
				"predicate": "info:fedora/fedora-system:def/model#hasModel",
				"object": "info:fedora/emory-control:ScannedVolume-1.0"
			},
			{
				"predicate": "http://pid.emory.edu/ns/2011/repo-management/#startPage",
				"object": "2"
			},
			{
				"predicate": "http://pid.emory.edu/ns/2011/repo-management/#hasPrimaryImage",
				"object": "info:fedora/%s_Readux_VirtualPage_1" % (pid_prefix)
			},			
			{
				"predicate": "info:fedora/fedora-system:def/relations-external#isConstituentOf",
				"object": "info:fedora/%s_Readux_VirtualBook" % (pid_prefix)
			},
			
			# WSUDOR related
			{
				"predicate": "http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isVirtual",
				"object": "True"
			},
			{
				"predicate": "http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isVirtualFor",
				"object": "info:fedora/%s" % wsudor_book.pid
			},
			{
				"predicate": "http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/hasSecurityPolicy",
				"object": "info:fedora/wayne:WSUDORSecurity-permit-apia-unrestricted"
			}
		]

		# write explicit RELS-EXT relationships			
		for relationship in object_relationships:
			print "Writing relationship:",str(relationship['predicate']),str(relationship['object'])
			self.add_relationship(str(relationship['predicate']),str(relationship['object']))


		# Content Type Unique
		###############################################################

		# OCR
		'''
		Merge alto XMLs 
		BLUFF FOR NOW
		'''
		print "Writing METS ALTO XML"
		ocr_handle = eulfedora.models.DatastreamObject(self, "OCR", "Fulltext PDF for item", mimetype="text/xml", control_group='M')
		ocr_handle.label = "OCR from Abbyy"
		ocr_handle.content = "</empty>"
		ocr_handle.save()


		# PDF
		print "Writing full-text PDF"
		pdf_handle = eulfedora.models.DatastreamObject(self, "PDF", "Fulltext PDF for item", mimetype="application/pdf", control_group='E')
		pdf_handle.ds_location = "http://localhost/fedora/objects/%s/datastreams/PDF_FULL/content" % (wsudor_book.pid) 
		pdf_handle.label = "Fulltext PDF for item"
		pdf_handle.save()

		###############################################################


		# save new object
		self.save()


# Virtual Readux Page Object
class WSUDOR_Readux_VirtualPage(DigitalObject):

	target_datastreams = {
		"text" : {
			"mimetype":"application/x-empty",
			"label":"page text"
		},
		"DC" : {
			"mimetype":"text/xml",
			"label":"Dublin Core"
		},
		"position" : {
			"mimetype":"text/plain",
			"label":"word positions"
		},
		"source-image" : {
			"mimetype":"image/jp2",
			"label":"Source Image"
		},
		"tei" : {
			"mimetype":"text/xml",
			"label":"TEI"
		},
		"RELS-EXT" : {
			"mimetype":"application/rdf+xml",
			"label":"RELS-EXT"
		}
	}

	'''
	This create function expets a page dictionary with:
		- order
		- JP2 info
		- alto XML
	'''

	def create(self, wsudor_book, page):
		
		'''
		Create Readux virtual Volume object based on WSUDOR_WSUebook
		'''

		# PID
		pid_prefix = wsudor_book.pid
		self.pid = pid_prefix + "_Readux_VirtualPage_%s" % (page['order'])

		# init
		print "Initializing %s" % (self.pid)
		self.save()

		# Dublin Core
		'''
		Will need to write this a bit more carefull - including the PID of this new object!
		'''

		# write POLICY datastream
		# NOTE: 'E' management type required, not 'R'
		print "Using policy:",wsudor_book.objMeta['policy']
		policy_suffix = wsudor_book.objMeta['policy'].split("info:fedora/")[1]
		policy_handle = eulfedora.models.DatastreamObject(self,"POLICY", "POLICY", mimetype="text/xml", control_group="E")
		policy_handle.ds_location = "http://localhost/fedora/objects/%s/datastreams/POLICY_XML/content" % (policy_suffix)
		policy_handle.label = "POLICY"
		policy_handle.save()

		
		# label
		self.label = "%s / %s" % (wsudor_book.ohandle.label,page['order'])

		# Build RELS-EXT
		object_relationships = [

			# Readux specific
			{
				"predicate": "info:fedora/fedora-system:def/model#hasModel",
				"object": "info:fedora/emory-control:ScannedPage-1.0"
			},
			{
				"predicate": "info:fedora/fedora-system:def/model#hasModel",
				"object": "info:fedora/emory-control:Image-1.0"
			},
			{
				"predicate": "http://pid.emory.edu/ns/2011/repo-management/#pageOrder",
				"object": page['order']
			},						
			{
				"predicate": "info:fedora/fedora-system:def/relations-external#isConstituentOf",
				"object": "info:fedora/%s_Readux_VirtualVolume" % (pid_prefix)
			},
			
			# WSUDOR related
			{
				"predicate": "http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isVirtual",
				"object": "True"
			},
			{
				"predicate": "http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isVirtualFor",
				"object": "info:fedora/%s" % wsudor_book.pid
			},
			{
				"predicate": "http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/hasSecurityPolicy",
				"object": "info:fedora/wayne:WSUDORSecurity-permit-apia-unrestricted"
			}
		]

		# write explicit RELS-EXT relationships			
		for relationship in object_relationships:
			print "Writing relationship:",str(relationship['predicate']),str(relationship['object'])
			self.add_relationship(str(relationship['predicate']),str(relationship['object']))


		# Content Type Unique
		###############################################################

		# source-image
		print "Linking Image"
		source_image_handle = eulfedora.models.DatastreamObject(self,"source-image", "source-image", mimetype="image/jp2", control_group="E")
		source_image_handle.ds_location = "http://localhost/fedora/objects/%s/datastreams/IMAGE_%s_JP2/content" % (wsudor_book.pid, page['order'])
		source_image_handle.label = "source-image"
		source_image_handle.save()

		# text
		print "Writing 'text' datastream"
		text_handle = eulfedora.models.DatastreamObject(self, "text", "text", mimetype="text/plain", control_group='M')
		text_handle.label = "text"
		text_handle.content = "There shall be text."
		text_handle.save()

		# position
		print "Writing 'position' datastream"
		position_handle = eulfedora.models.DatastreamObject(self, "position", "position", mimetype="text/plain", control_group='M')
		position_handle.label = "position"
		position_handle.content = "There shall be position."
		position_handle.save()

		# tei
		print "Writing 'tei' datastream"
		tei_handle = eulfedora.models.DatastreamObject(self, "tei", "tei", mimetype="text/xml", control_group='M')
		tei_handle.label = "tei"
		tei_handle.content = "</empty>"
		tei_handle.save()

		###############################################################


		# save new object
		self.save()




