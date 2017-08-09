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
import requests

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
from WSUDOR_Manager import redisHandles, helpers, models


class WSUDOR_Document(WSUDOR_ContentTypes.WSUDOR_GenObject):

	# static values for class
	label = "Document"
	description = "This ContentType applies to what we commonly think of as 'documents', including PDFs, Word docs, Open Office, etc.  The intent is to create a representative thumbnail for this item, and a derivative, access PDF."
	Fedora_ContentType = "CM:Document"
	version = 1

	def __init__(self,object_type=False,content_type=False,payload=False,orig_payload=False):
		
		# run __init__ from parent class
		WSUDOR_ContentTypes.WSUDOR_GenObject.__init__(self,object_type, content_type, payload, orig_payload)
		
		# Add WSUDOR_Document struct_requirements to WSUDOR_Object instance struct_requirements
		self.struct_requirements['WSUDOR_Document'] = {
			"datastreams":[],
			"external_relationships":[]
		}

		# content-type methods run and returned to API
		self.public_api_additions = [self.object_hierarchy]

		# OAIexposed (on ingest, register OAI identifier)
		self.OAIexposed = True


	# perform ingestTest
	def validIngestBag(self, indexObject=True):

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
	def ingestBag(self, indexObject=True):

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
				logging.debug("Writing relationship: %s %s" % (str(relationship['predicate']),str(relationship['object'])))
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
			if len(self.objMeta['datastreams']) > 0:
				self.ohandle.add_relationship("http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isDiscoverable","info:fedora/True")
			else:
				self.ohandle.add_relationship("http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isDiscoverable","info:fedora/False")

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
    <mods:title>%s</mods:title>
  </mods:titleInfo>
  <mods:identifier type="local">%s</mods:identifier>
  <mods:extension>
    <PID>%s</PID>
  </mods:extension>
</mods:mods>
				''' % (self.objMeta['label'], self.objMeta['id'].split(":")[1], self.objMeta['id'])
				logging.debug("%s" % raw_MODS)
				MODS_handle.content = raw_MODS		
				MODS_handle.save()


			# write PREMIS if exists
			if os.path.exists(self.Bag.path + "/data/PREMIS.xml"):
				logging.debug("writing PREMIS datastream")
				PREMIS_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "PREMIS", "PREMIS preservation metadadta", mimetype="text/xml", control_group='M')
				PREMIS_handle.label = "PREMIS preservation metadadta"
				premis_file_path = self.Bag.path + "/data/PREMIS.xml"
				PREMIS_handle.content = open(premis_file_path)
				PREMIS_handle.save()


			# create derivatives and write datastreams
			for ds in self.objMeta['datastreams']:

				# set file_path
				file_path = self.Bag.path + "/data/datastreams/" + ds['filename']
				logging.debug("Operating on: %s" % file_path)

				# original
				orig_handle = eulfedora.models.FileDatastreamObject(self.ohandle, ds['ds_id'], ds['label'], mimetype=ds['mimetype'], control_group='M')
				orig_handle.label = ds['label']
				orig_handle.content = open(file_path)
				orig_handle.save()


				# make thumb for PDF				
				if ds['mimetype'] == "application/pdf":

					# writing FILE datastream
					rep_handle = eulfedora.models.DatastreamObject(self.ohandle, "FILE", "FILE", mimetype=ds['mimetype'], control_group="E")
					rep_handle.ds_location = "http://localhost/fedora/objects/%s/datastreams/%s/content" % (self.ohandle.pid, ds['ds_id'])
					rep_handle.label = "FILE"
					rep_handle.save()

					logging.debug("Creating derivative thumbnail from PDF")
					# thumb if incoming file as pdf							
					temp_filename = "/tmp/Ouroboros/"+str(uuid.uuid4())+".jpg"
					os.system('convert -thumbnail 200x200 -background white %s[0] %s' % (file_path, temp_filename))
					thumb_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "%s_THUMBNAIL" % (ds['ds_id']), "%s_THUMBNAIL" % (ds['label']), mimetype="image/jpeg", control_group='M')
					thumb_handle.label = "%s_THUMBNAIL" % (ds['label'])
					thumb_handle.content = open(temp_filename)
					thumb_handle.save()
					os.system('rm %s' % (temp_filename))

					logging.debug("Creating derivative preview from PDF")
					# thumb if incoming file as pdf							
					temp_filename = "/tmp/Ouroboros/"+str(uuid.uuid4())+".jpg"
					os.system('convert -thumbnail 960x960 -background white %s[0] %s' % (file_path, temp_filename))
					thumb_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "%s_PREVIEW" % (ds['ds_id']), "%s_PREVIEW" % (ds['label']), mimetype="image/jpeg", control_group='M')
					thumb_handle.label = "%s_PREVIEW" % (ds['label'])
					thumb_handle.content = open(temp_filename)
					thumb_handle.save()
					os.system('rm %s' % (temp_filename))


				# create derivative FILE datastream with appropriate converter
				# CONSIDER REWORKING AS RECIPES A LA PRINCETON'S KAKADU JP2 RECIPES
				else:					

					oo_formats = [
						'application/vnd.oasis.opendocument.text',
						'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
					]
					if ds['mimetype'] in oo_formats:

						# create PDF deriv for Word Doc
						deriv_PDF = '/tmp/Ouroboros/%s.pdf' % ds['filename'].split(".")[0] # assumes no period in datastream id...
						cmd = 'soffice --headless --convert-to pdf --outdir /tmp/Ouroboros %s' % file_path
						logging.debug("%s" % cmd)
						os.system(cmd)

						# write derivative PDF for FILE datastream
						orig_handle = eulfedora.models.FileDatastreamObject(self.ohandle, 'FILE', 'FILE', mimetype='application/pdf', control_group='M')
						orig_handle.label = 'FILE'
						orig_handle.content = open(deriv_PDF)
						orig_handle.save()

						temp_filename = "/tmp/Ouroboros/"+str(uuid.uuid4())+".jpg"
						os.system('convert -thumbnail 200x200 -background white %s[0] %s' % (deriv_PDF, temp_filename))
						thumb_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "%s_THUMBNAIL" % (ds['ds_id']), "%s_THUMBNAIL" % (ds['label']), mimetype="image/jpeg", control_group='M')
						thumb_handle.label = "%s_THUMBNAIL" % (ds['label'])
						thumb_handle.content = open(temp_filename)
						thumb_handle.save()
						os.system('rm %s' % (temp_filename))


				# write generic thumbnail for what should be SINGLE file per object
				for gen_type in ['THUMBNAIL','PREVIEW']:
					rep_handle = eulfedora.models.DatastreamObject(self.ohandle, gen_type, gen_type, mimetype="image/jpeg", control_group="M")
					rep_handle.ds_location = "http://localhost/fedora/objects/%s/datastreams/%s_%s/content" % (self.ohandle.pid, self.objMeta['isRepresentedBy'], gen_type)
					rep_handle.label = gen_type
					rep_handle.save()

			# save and commit object before finishIngest()
			final_save = self.ohandle.save()

			# finish generic ingest
			return self.finishIngest(gen_manifest=False, indexObject=indexObject, contentTypeMethods=[])



		# exception handling
		except Exception,e:
			logging.debug("%s" % traceback.format_exc())
			logging.debug("Image Ingest Error: %s" % e)
			return False


	# ingest image type
	def genIIIFManifest(self, iiif_manifest_factory_instance, identifier, getParams):

		pass


	# ingest image type
	def genPreview(self):

		# writing FILE datastream
		deriv_PDF = "/tmp/Ouroboros/"+str(uuid.uuid4())+".pdf"
		with open(deriv_PDF, 'w') as f:
			file_handle = self.ohandle.getDatastreamObject('FILE')
			f.write(file_handle.content)

		temp_filename = "/tmp/Ouroboros/"+str(uuid.uuid4())+".jpg"
		os.system('convert -thumbnail 960x960 -background white %s[0] %s' % (deriv_PDF, temp_filename))
		preview_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "PREVIEW", "PREVIEW", mimetype="image/jpeg", control_group='M')
		preview_handle.label = "PREVIEW"
		preview_handle.content = open(temp_filename)
		preview_handle.save()
		os.system('rm %s' % (temp_filename))
		os.system('rm %s' % (deriv_PDF))


	# default previewImage return
	def previewImage(self):

		'''
		Return image/loris params for API to render
			- pid, datastream, region, size, rotation, quality, format
		'''
		return (self.pid, 'PREVIEW', 'full', 'full', 0, 'default', 'jpg')


	# content-type specific indexing tasks
	def index_augment(self):

		logging.debug("######### content-type specific indexing for Document ############")

		# get all PDF's
		pdf_ds_list = [ 
			ds for ds in self.ohandle.ds_list 
			if self.ohandle.ds_list[ds].mimeType == "application/pdf" 
			and self.ohandle.getDatastreamObject(ds).control_group != 'R'
			and ds != "FILE"
		]
		logging.debug(pdf_ds_list)

		# iterate through and add to list
		if len(pdf_ds_list) > 0:
			
			# start list of full-text to index
			self.SolrDoc.doc.int_fullText = []
			
			# iterate through and appsend
			for pdf in pdf_ds_list:
				
				# get handle
				pdf_ds_handle = self.ohandle.getDatastreamObject(pdf)

				# use alternate form for extracting text
				temp_pdf = "/tmp/Ouroboros/%s.pdf" % str(uuid.uuid4())
				temp_txt = "/tmp/Ouroboros/%s.txt" % str(uuid.uuid4())
				with open(temp_pdf,'wb') as f:
					f.write(pdf_ds_handle.content)
				os.system('pdftotext %s %s' % (temp_pdf,temp_txt))
				with open(temp_txt,'r') as f:
					ds_stripped_content = f.read()
				# cleanup
				os.remove(temp_pdf)
				os.remove(temp_txt)

				logging.debug(ds_stripped_content)

				# add to list
				self.SolrDoc.doc.int_fullText.append(ds_stripped_content)


	# content_type refresh
	def refresh_content_type(self):

		# figure hierarchy
		self.object_hierarchy(overwrite=True)


