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
from WSUDOR_Manager.solrHandles import solr_handle
from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager import redisHandles, helpers


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
		self.public_api_additions = []


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
			print "Using policy:",self.objMeta['policy']
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
				print "Writing relationship:",str(relationship['predicate']),str(relationship['object'])
				self.ohandle.add_relationship(str(relationship['predicate']),str(relationship['object']))
			
			# writes derived RELS-EXT
			# isRepresentedBy
			self.ohandle.add_relationship("http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isRepresentedBy",self.objMeta['isRepresentedBy'])
			
			# hasContentModel
			content_type_string = str("info:fedora/CM:"+self.objMeta['content_type'].split("_")[1])
			print "Writing ContentType relationship:","info:fedora/fedora-system:def/relations-external#hasContentModel",content_type_string
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
				print raw_MODS
				MODS_handle.content = raw_MODS		
				MODS_handle.save()


			# write PREMIS if exists
			if os.path.exists(self.Bag.path + "/data/PREMIS.xml"):
				print "writing PREMIS datastream"
				PREMIS_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "PREMIS", "PREMIS preservation metadadta", mimetype="text/xml", control_group='M')
				PREMIS_handle.label = "PREMIS preservation metadadta"
				premis_file_path = self.Bag.path + "/data/PREMIS.xml"
				PREMIS_handle.content = open(premis_file_path)
				PREMIS_handle.save()


			# create derivatives and write datastreams
			for ds in self.objMeta['datastreams']:

				# set file_path
				file_path = self.Bag.path + "/data/datastreams/" + ds['filename']
				print "Operating on:",file_path

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

					print "Creating derivative thumbnail from PDF"
					# thumb if incoming file as pdf							
					temp_filename = "/tmp/Ouroboros/"+str(uuid.uuid4())+".jpg"
					os.system('convert -thumbnail 200x200 -background white %s[0] %s' % (file_path, temp_filename))
					thumb_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "%s_THUMBNAIL" % (ds['ds_id']), "%s_THUMBNAIL" % (ds['label']), mimetype="image/jpeg", control_group='M')
					thumb_handle.label = "%s_THUMBNAIL" % (ds['label'])
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
						print cmd
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
				for gen_type in ['THUMBNAIL']:
					rep_handle = eulfedora.models.DatastreamObject(self.ohandle, gen_type, gen_type, mimetype="image/jpeg", control_group="M")
					rep_handle.ds_location = "http://localhost/fedora/objects/%s/datastreams/%s_%s/content" % (self.ohandle.pid, self.objMeta['isRepresentedBy'], gen_type)
					rep_handle.label = gen_type
					rep_handle.save()

			# save and commit object before finishIngest()
			final_save = self.ohandle.save()

			# finish generic ingest
			return self.finishIngest()



		# exception handling
		except Exception,e:
			print traceback.format_exc()
			print "Image Ingest Error:",e
			return False


	# ingest image type
	def genIIIFManifest(self, iiif_manifest_factory_instance, identifier, getParams):

		pass














