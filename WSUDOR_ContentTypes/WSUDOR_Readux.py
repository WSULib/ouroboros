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

# rdflib
import rdflib
from rdflib.namespace import XSD, RDF, Namespace

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


# RDF namespaces
emory = Namespace(rdflib.URIRef('http://pid.emory.edu/ns/2011/repo-management/#'))
wsudor = Namespace(rdflib.URIRef('http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/'))


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
		self.pid = wsudor_book.pid + "_Readux_VirtualBook"

		# init
		print "Initializing %s" % (self.pid)
		self.save()

		# Dublin Core
		self.dc.content = wsudor_book.ohandle.dc.content
		self.dc.save()

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

		# bind namespaces
		self.rels_ext.content.bind('eul-repomgmt',emory)
		self.rels_ext.content.bind('wsudor',wsudor)

		object_relationships = [
			{
				"predicate": rdflib.term.URIRef("info:fedora/fedora-system:def/model#hasModel"),
				"object": rdflib.term.URIRef("info:fedora/emory-control:ScannedBook-1.0")
			},
			{
				"predicate": rdflib.term.URIRef("info:fedora/fedora-system:def/relations-external#isMemberOfCollection"),
				"object": rdflib.term.URIRef("info:fedora/wayne:collectionWSUebooks")
			},
			{
				"predicate": rdflib.term.URIRef("info:fedora/fedora-system:def/relations-external#hasConstituent"),
				"object": rdflib.term.URIRef("info:fedora/%s_Readux_VirtualVolume" % (wsudor_book.pid))
			},
			{
				"predicate": wsudor.isVirtual,
				"object": rdflib.term.Literal("True")
			},
			{
				"predicate": wsudor.isVirtualFor,
				"object": rdflib.term.URIRef("info:fedora/%s" % wsudor_book.pid)
			},
			{
				"predicate": wsudor.hasSecurityPolicy,
				"object": rdflib.term.URIRef("info:fedora/wayne:WSUDORSecurity-permit-apia-unrestricted")
			}
		]

		for r in object_relationships:
			self.rels_ext.content.set((rdflib.term.URIRef('info:fedora/%s' % self.pid), r['predicate'], r['object']))

		self.rels_ext.save()



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
		self.dc.content = wsudor_book.ohandle.dc.content
		self.dc.save()

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
		self.rels_ext.content.bind('eul-repomgmt',emory)
		self.rels_ext.content.bind('wsudor',wsudor)

		object_relationships = [
			{
				"predicate": rdflib.term.URIRef("info:fedora/fedora-system:def/model#hasModel"),
				"object": rdflib.term.URIRef("info:fedora/emory-control:ScannedVolume-1.1")
			},
			{
				"predicate": emory.hasPrimaryImage,
				"object": rdflib.term.URIRef("info:fedora/%s_Readux_VirtualPage_1" % (pid_prefix))
			},			
			{
				"predicate": rdflib.term.URIRef("info:fedora/fedora-system:def/relations-external#isConstituentOf"),
				"object": rdflib.term.URIRef("info:fedora/%s_Readux_VirtualBook" % (pid_prefix))
			},
			{
				"predicate": wsudor.isVirtual,
				"object": rdflib.term.Literal("True")
			},
			{
				"predicate": wsudor.isVirtualFor,
				"object": rdflib.term.URIRef("info:fedora/%s" % wsudor_book.pid)
			},
			{
				"predicate": wsudor.hasSecurityPolicy,
				"object": rdflib.term.URIRef("info:fedora/wayne:WSUDORSecurity-permit-apia-unrestricted")
			}
		]

		for r in object_relationships:
			self.rels_ext.content.set((rdflib.term.URIRef('info:fedora/%s' % self.pid), r['predicate'], r['object']))

		self.rels_ext.save()


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
		'''
		problem here with approach: relationships with same predicate are over-writing each other
		'''
		self.rels_ext.content.bind('eul-repomgmt',emory)
		self.rels_ext.content.bind('wsudor',wsudor)

		object_relationships = [
			{
				"predicate": rdflib.term.URIRef("info:fedora/fedora-system:def/model#hasModel"),
				"object": rdflib.term.URIRef("info:fedora/emory-control:Image-1.0")
			},
			{
				"predicate": rdflib.term.URIRef("info:fedora/fedora-system:def/model#hasModel"),
				"object": rdflib.term.URIRef("info:fedora/emory-control:ScannedPage-1.1")
			},
			{
				"predicate": emory.pageOrder,
				"object": rdflib.term.Literal(page['order'], datatype=rdflib.term.URIRef(u'http://www.w3.org/2001/XMLSchema#int'))
			},						
			{
				"predicate": rdflib.term.URIRef("info:fedora/fedora-system:def/relations-external#isConstituentOf"),
				"object": rdflib.term.URIRef("info:fedora/%s_Readux_VirtualVolume" % (pid_prefix))
			},
			{
				"predicate": wsudor.isVirtual,
				"object": rdflib.term.Literal("True")
			},
			{
				"predicate": wsudor.isVirtualFor,
				"object": rdflib.term.URIRef("info:fedora/%s" % wsudor_book.pid)
			},
			{
				"predicate": wsudor.hasSecurityPolicy,
				"object": rdflib.term.URIRef("info:fedora/wayne:WSUDORSecurity-permit-apia-unrestricted")
			}
		]

		for r in object_relationships:
			self.rels_ext.content.set((rdflib.term.URIRef('info:fedora/%s' % self.pid), r['predicate'], r['object']))

		self.rels_ext.save()


		# Content Type Unique
		###############################################################

		# source-image
		print "Linking Image"
		source_image_handle = eulfedora.models.DatastreamObject(self,"source-image", "source-image", mimetype="image/jp2", control_group="E")
		source_image_handle.ds_location = "http://localhost/fedora/objects/%s/datastreams/IMAGE_%s_JP2/content" % (wsudor_book.pid, page['order'])
		source_image_handle.label = "source-image"
		source_image_handle.save()

		# text
		print "Writing 'text' datastream, aka 'alto'"
		alto_handle = eulfedora.models.DatastreamObject(self, "text", "text", mimetype="text/xml", control_group='M')
		alto_handle.ds_location = "http://localhost/fedora/objects/%s/datastreams/ALTOXML_%s/content" % (wsudor_book.pid, page['order'])
		alto_handle.label = "text"
		alto_handle.save()

		# tei
		# print "Writing 'tei' datastream"
		# tei_handle = eulfedora.models.DatastreamObject(self, "tei", "tei", mimetype="text/xml", control_group='M')
		# tei_handle.label = "tei"
		# tei_handle.content = "</empty>"
		# tei_handle.save()

		###############################################################

		# save new object
		self.save()




