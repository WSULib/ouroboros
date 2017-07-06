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

# library for working with LOC BagIt standard 
import bagit

# celery
from WSUDOR_Manager import celery

# eulfedora
import eulfedora

# localConfig
import localConfig

# WSUDOR
import WSUDOR_ContentTypes
from WSUDOR_ContentTypes import logging
logging = logging.getChild("WSUDOR_Object")
from WSUDOR_Manager.solrHandles import solr_handle
from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager import redisHandles, helpers


class WSUDOR_LearningObject(WSUDOR_ContentTypes.WSUDOR_GenObject):

	# static values for class
	label = "Learning Object"
	description = "This ContentType represents a Learning Object for collections.  Usually associated with objects in the collection, not but not required, it provides teaching resources associated with the collection."
	Fedora_ContentType = "CM:LearningObject"
	version = 1

	def __init__(self,object_type=False,content_type=False,payload=False,orig_payload=False):
		
		# run __init__ from parent class
		WSUDOR_ContentTypes.WSUDOR_GenObject.__init__(self,object_type, content_type, payload, orig_payload)
		
		# Add WSUDOR_LearningObject struct_requirements to WSUDOR_Object instance struct_requirements
		self.struct_requirements['WSUDOR_LearningObject'] = {
			"datastreams":[],
			"external_relationships":[]
		}

		# content-type methods run and returned to API
		self.public_api_additions = []

		# OAIexposed (on ingest, register OAI identifier)
		self.OAIexposed = True


	# perform ingestTest
	def validIngestBag(self,indexObject=True):

		def report_failure(failure_tuple):
			if results_dict['verdict'] == True : results_dict['verdict'] = False
			results_dict['failed_tests'].append(failure_tuple)

		# reporting
		results_dict = {
			"verdict":True,
			"failed_tests":[]
		}

		# check that content_type is a valid ContentType				
		if self.__class__ not in WSUDOR_ContentTypes.WSUDOR_GenObject.__subclasses__():
			report_failure(("Valid ContentType","WSUDOR_Object instance's ContentType: %s, not found in acceptable ContentTypes: %s " % (self.content_type, WSUDOR_ContentTypes.WSUDOR_GenObject.__subclasses__())))

		# finally, return verdict
		return results_dict


	# ingest image type
	@helpers.timing
	def ingestBag(self):

		if self.object_type != "bag":
			raise Exception("WSUDOR_Object instance is not 'bag' type, aborting.")


		# attempt to ingest bag / object
		try:		
			
			self.ohandle = fedora_handle.get_object(self.objMeta['id'],create=True)
			self.ohandle.save()

			# set base properties of object
			self.ohandle.label = self.objMeta['label']

			# write POLICY datastream
			# NOTE: 'E' management type required, not 'R'
			logging.debug("Using policy: %s" % self.objMeta['policy'])
			policy_suffix = self.objMeta['policy'].split("info:fedora/")[1]
			policy_handle = eulfedora.models.DatastreamObject(self.ohandle,"POLICY", "POLICY", mimetype="text/xml", control_group="E")
			policy_handle.ds_location = "http://localhost/fedora/objects/%s/datastreams/POLICY_XML/content" % (policy_suffix)
			policy_handle.label = "POLICY"
			policy_handle.save()

			# write objMeta as datastream
			objMeta_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "OBJMETA", "Ingest Bag Object Metadata", mimetype="application/json", control_group='M')
			objMeta_handle.label = "Ingest Bag Object Metadata"
			file_path = self.Bag.path + "/data/objMeta.json"
			objMeta_handle.content = open(file_path)
			objMeta_handle.save()

			# write explicit RELS-EXT relationships
			for relationship in self.objMeta['object_relationships']:
				logging.debug("Writing relationship: %s %s" (str(relationship['predicate']),str(relationship['object'])))
				self.ohandle.add_relationship(str(relationship['predicate']),str(relationship['object']))
			
			# writes derived RELS-EXT
			# isRepresentedBy
			'''
			if present, isRepresentedBy relationship from objMeta trumps pre-existing relationships
			'''
			if 'isRepresentedBy' in self.objMeta.keys():
				# purge old ones
				for s,p,o in self.ohandle.rels_ext.content:
					if str(p) == 'http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isRepresentedBy':
						logging.debug('found pre-existing isRepresentedBy relationship, %s, removing as we have one from objMeta' % str(o))
						self.ohandle.purge_relationship('http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isRepresentedBy',o)
				logging.debug("writing isRepresentedBy from objMeta: %s" % self.objMeta['isRepresentedBy'])
				self.ohandle.add_relationship("http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isRepresentedBy",self.objMeta['isRepresentedBy'])
			
			# hasContentModel
			content_type_string = str("info:fedora/CM:"+self.objMeta['content_type'].split("_")[1])
			logging.debug("Writing ContentType relationship: info:fedora/fedora-system:def/relations-external#hasContentModel %s" % content_type_string)
			self.ohandle.add_relationship("info:fedora/fedora-system:def/relations-external#hasContentModel",content_type_string)
			self.ohandle.add_relationship("http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/preferredContentModel",content_type_string)

			# set discoverability if datastreams present
			self.ohandle.add_relationship("http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isDiscoverable","info:fedora/True")

			# write MODS datastream if MODS.xml exists
			if os.path.exists(self.Bag.path + "/data/MODS.xml"):
				MODS_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "MODS", "MODS descriptive metadata", mimetype="text/xml", control_group='M')
				MODS_handle.label = "MODS descriptive metadata"
				file_path = self.Bag.path + "/data/MODS.xml"
				MODS_handle.content = open(file_path)
				MODS_handle.save()

			else:
				# write generic MODS datastream
				MODS_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "MODS", "MODS descriptive metadata", mimetype="text/xml", control_group='M')
				MODS_handle.label = "MODS descriptive metadata"

				raw_MODS = '''
<mods:mods xmlns:mods="http://www.loc.gov/mods/v3" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="3.4" xsi:schemaLocation="http://www.loc.gov/mods/v3 http://www.loc.gov/standards/mods/v3/mods-3-4.xsd">
  <mods:titleInfo>
    <mods:title>%(label)s</mods:title>
  </mods:titleInfo>
  <mods:abstract>%(description)s</mods:abstract>
  <mods:originInfo>
  	<mods:dateCreated>%(date)s</mods:dateCreated>
  </mods:originInfo>
  <mods:identifier type="local">%(identifier)s</mods:identifier>
  <mods:extension>
    <PID>%(id)s</PID>
  </mods:extension>
</mods:mods>
				''' % {
						'label':self.objMeta['label'],
						'description':self.objMeta['description'],
						'date':self.objMeta['date'],
						'id':self.objMeta['id'],
						'identifier':self.objMeta['identifier'],
					}
				logging.debug("%s" % raw_MODS)
				MODS_handle.content = raw_MODS		
				MODS_handle.save()

			# write generic thumbnail for what should be SINGLE file per object
			rep_handle = eulfedora.models.DatastreamObject(self.ohandle, 'THUMBNAIL', 'THUMBNAIL', mimetype="image/jpeg", control_group="M")
			rep_handle.ds_location = "http://localhost/fedora/objects/wayne:WSUDORThumbnails/datastreams/WSUDOR_LearningObject/content"
			rep_handle.label = 'THUMBNAIL'
			rep_handle.save()

			# save and commit object before finishIngest()
			final_save = self.ohandle.save()

			# finish generic ingest
			return self.finishIngest()

		# exception handling
		except Exception,e:
			logging.debug("%s" % traceback.format_exc())
			logging.debug("Image Ingest Error: %s" % e)
			return False


	# ingest image type
	def genIIIFManifest(self, iiif_manifest_factory_instance, identifier, getParams):

		pass














