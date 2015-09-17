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
from cl.cl import celery

# eulfedora
import eulfedora

# WSUDOR
import WSUDOR_ContentTypes
from WSUDOR_Manager.solrHandles import solr_handle
from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager import redisHandles, helpers


class WSUDOR_HierarchicalFiles(WSUDOR_ContentTypes.WSUDOR_GenObject):

	# static values for class
	label = "Hierarchical File"

	description = "Still under development.  The Hierarchical File Content Type is meant to model content where the filesystem / archival hierarchical order is important for understanding the object."

	Fedora_ContentType = "CM:HierarchicalFiles"

	def __init__(self,object_type=False,content_type=False,payload=False):
		
		# run __init__ from parent class
		WSUDOR_ContentTypes.WSUDOR_GenObject.__init__(self,object_type, content_type, payload)
		
		# Add WSUDOR_HierarchicalFiles struct_requirements to WSUDOR_Object instance struct_requirements
		self.struct_requirements['WSUDOR_HierarchicalFiles'] = {
			"datastreams":[],
			"external_relationships":[]
		}


	# perform ingestTest
	def validIngestBag(self):

		def report_failure(failure_tuple):
			if results_dict['verdict'] == True : results_dict['verdict'] = False
			results_dict['failed_tests'].append(failure_tuple)

		# reporting
		results_dict = {
			"verdict":True,
			"failed_tests":[]
		}

		# check that 'isRepresentedBy' datastream exists in self.objMeta.datastreams[]
		# ds_ids = [each['ds_id'] for each in self.objMeta['datastreams']]
		# if self.objMeta['isRepresentedBy'] not in ds_ids:
		# 	report_failure(("isRepresentedBy_check","{isRep} is not in {ds_ids}".format(isRep=self.objMeta['isRepresentedBy'],ds_ids=ds_ids)))


		# check that content_type is a valid ContentType				
		if self.__class__ not in WSUDOR_ContentTypes.WSUDOR_GenObject.__subclasses__():
			report_failure(("Valid ContentType","WSUDOR_Object instance's ContentType: {content_type}, not found in acceptable ContentTypes: {ContentTypes_list} ".format(content_type=self.content_type,ContentTypes_list=WSUDOR_ContentTypes.WSUDOR_GenObject.__subclasses__())))


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
			policy_handle.ds_location = "http://localhost/fedora/objects/{policy}/datastreams/POLICY_XML/content".format(policy=policy_suffix)
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

			# write MODS datastream
			MODS_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "MODS", "MODS descriptive metadata", mimetype="text/xml", control_group='M')
			MODS_handle.label = "MODS descriptive metadata"

			raw_MODS = '''
<mods:mods xmlns:mods="http://www.loc.gov/mods/v3" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="3.4" xsi:schemaLocation="http://www.loc.gov/mods/v3 http://www.loc.gov/standards/mods/v3/mods-3-4.xsd">
  <mods:titleInfo>
    <mods:title>{label}</mods:title>
  </mods:titleInfo>
  <mods:identifier type="local">{identifier}</mods:identifier>
  <mods:extension>
    <PID>{PID}</PID>
  </mods:extension>
</mods:mods>
			'''.format(label=self.objMeta['label'], identifier=self.objMeta['id'].split(":")[1], PID=self.objMeta['id'])
			print raw_MODS
			MODS_handle.content = raw_MODS		
			MODS_handle.save()

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

				# write gen FILE datastream
				rep_handle = eulfedora.models.DatastreamObject(self.ohandle, "FILE", "FILE", mimetype=ds['mimetype'], control_group="R")
				rep_handle.ds_location = "http://digital.library.wayne.edu/fedora/objects/{pid}/datastreams/{ds_id}/content".format(pid=self.ohandle.pid,ds_id=ds['ds_id'])
				rep_handle.label = "FILE"
				rep_handle.save()

				# make thumb for PDF
				if ds['mimetype'] == "application/pdf":
					print "Creating derivative thumbnail from PDF"					
					temp_filename = "/tmp/Ouroboros/"+str(uuid.uuid4())+".jpg"
					os.system('convert -thumbnail 200x200 -background white {file_path}[0] {temp_filename}'.format(file_path=file_path,temp_filename=temp_filename))
					thumb_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "{ds_id}_THUMBNAIL".format(ds_id=ds['ds_id']), "{label}_THUMBNAIL".format(label=ds['label']), mimetype="image/jpeg", control_group='M')
					thumb_handle.label = "{label}_THUMBNAIL".format(label=ds['label'])
					thumb_handle.content = open(temp_filename)
					thumb_handle.save()
					os.system('rm {temp_filename}'.format(temp_filename=temp_filename))

					# write generic thumbnail for what should be SINGLE file per object
					for gen_type in ['THUMBNAIL']:
						rep_handle = eulfedora.models.DatastreamObject(self.ohandle, gen_type, gen_type, mimetype="image/jpeg", control_group="R")
						rep_handle.ds_location = "http://digital.library.wayne.edu/fedora/objects/{pid}/datastreams/{ds_id}_{gen_type}/content".format(pid=self.ohandle.pid,ds_id=self.objMeta['isRepresentedBy'],gen_type=gen_type)
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



























