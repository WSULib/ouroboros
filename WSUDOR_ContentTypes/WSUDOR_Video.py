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

# localConfig
import localConfig




class WSUDOR_Video(WSUDOR_ContentTypes.WSUDOR_GenObject):

	# static values for class
	label = "Video"

	description = "Video object type."

	Fedora_ContentType = "CM:Video"

	def __init__(self,object_type=False,content_type=False,payload=False,orig_payload=False):
		
		# run __init__ from parent class
		WSUDOR_ContentTypes.WSUDOR_GenObject.__init__(self,object_type, content_type, payload, orig_payload)
		
		# Add WSUDOR_Video struct_requirements to WSUDOR_Object instance struct_requirements
		self.struct_requirements['WSUDOR_Video'] = {
			"datastreams":[
				{
					"id":"*_MP4",
					"purpose":"Access MP4 derivative",
					"mimetype":"audio/mpeg"
				}				
			],
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
		ds_ids = [each['ds_id'] for each in self.objMeta['datastreams']]
		if self.objMeta['isRepresentedBy'] not in ds_ids:
			report_failure(("isRepresentedBy_check","{isRep} is not in {ds_ids}".format(isRep=self.objMeta['isRepresentedBy'],ds_ids=ds_ids)))


		# check that content_type is a valid ContentType				
		if self.__class__ not in WSUDOR_ContentTypes.WSUDOR_GenObject.__subclasses__():
			report_failure(("Valid ContentType","WSUDOR_Object instance's ContentType: {content_type}, not found in acceptable ContentTypes: {ContentTypes_list} ".format(content_type=self.content_type,ContentTypes_list=WSUDOR_ContentTypes.WSUDOR_GenObject.__subclasses__())))


		# check that objMeta.id starts with "wayne:"
		# if not self.pid.startswith("wayne:"):
		# 	report_failure(("PID prefix","The pid {pid}, does not start with the usual 'wayne:' prefix.".format(pid=self.pid)))


		# check that objMeta.id is NOT already an object in WSUDOR
		# UPDATE : on back burner, Eulfedora seems to create a placeholder object in Fedora somehow...
		# ohandle = fedora_handle.get_object(self.pid)
		# if ohandle.exists == True:
		# 	report_failure(("PID existence in WSUDOR","The pid {pid}, appears to exist in WSUDOR already.".format(pid=self.pid)))						
		
		
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

			# determine isRepresentedBy filename
			for DS in self.objMeta['datastreams']:
				if DS['ds_id'] == self.objMeta['isRepresentedBy']:
					# isRepresentedBy_filename = DS['filename']
					isRepresentedBy_filepath = self.Bag.path + "/data/datastreams/" + DS['filename']
			
			# hasContentModel
			content_type_string = str("info:fedora/CM:"+self.objMeta['content_type'].split("_")[1])
			print "Writing ContentType relationship:","info:fedora/fedora-system:def/relations-external#hasContentModel",content_type_string
			self.ohandle.add_relationship("info:fedora/fedora-system:def/relations-external#hasContentModel",content_type_string)

			# write MODS datastream
			MODS_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "MODS", "MODS descriptive metadata", mimetype="text/xml", control_group='M')
			MODS_handle.label = "MODS descriptive metadata"
			file_path = self.Bag.path + "/data/MODS.xml"
			MODS_handle.content = open(file_path)
			MODS_handle.save()

			# prime PLAYLIST list of datastreams
			playlist_list = []

			# create derivatives and write datastreams
			count = 1
			for ds in self.objMeta['datastreams']:

				file_path = self.Bag.path + "/data/datastreams/" + ds['filename']
				print "Looking for:",file_path

				# if no 'order' key, or not integer (e.g. None), assign incrementing number
				if 'order' not in ds.keys() or not isinstance( ds['order'], int ):
					print "Could not find valid 'order' key for datastream dictionary, assigning",len(self.objMeta['datastreams']) + count
					ds['order'] = len(self.objMeta['datastreams']) + count
					# bump ds counter
					count += 1

				# original, untouched
				orig_handle = eulfedora.models.FileDatastreamObject(self.ohandle, ds['ds_id'], ds['label'], mimetype=ds['mimetype'], control_group='M')
				orig_handle.label = ds['label']
				orig_handle.content = open(file_path)
				orig_handle.save()

				# make mp3 derivative				
				temp_filename = "/tmp/Ouroboros/"+str(uuid.uuid4())+".mp3"
				audio_file_handle = VideoSegment.from_file(file_path)
				mp3_file_handle = audio_file_handle.export(temp_filename,format="mp3")
				mp3_file_handle.close()
				if os.path.getsize(temp_filename) < 1:
					print "Converted file is empty, could not create derivative MP3."
				else:
					print "Derivative mp3 created."
				mp3_ds_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "{ds_id}_MP3".format(ds_id=ds['ds_id']), "{label}_MP3".format(label=ds['label']), mimetype="audio/mpeg", control_group='M')
				mp3_ds_handle.label = ds['label']
				mp3_ds_handle.content = open(temp_filename)
				mp3_ds_handle.save()
				os.system('rm {temp_filename}'.format(temp_filename=temp_filename))		


				# create thumbnail and preview waveforms for datastreams
				'''
				Using BBC's audiowaveform:
				https://github.com/bbcrd/audiowaveform
				'''
				temp_filename = "/tmp/Ouroboros/"+str(uuid.uuid4())+".png"
				os.system("audiowaveform -i {input_file} -o {temp_filename} -w 1280 --waveform-color 0c5449ff --background-color FFFFFFFF --no-axis-labels".format(input_file=file_path, temp_filename=temp_filename))
				
				# preview (do first, downsizing from here)				
				im = Image.open(temp_filename)	
				width, height = im.size
				max_width = 1280	
				max_height = 960		
				im.save(temp_filename,"JPEG")
				rep_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "{ds_id}_PREVIEW".format(ds_id=ds['ds_id']), "{label}_PREVIEW".format(label=ds['label']), mimetype="image/jpeg", control_group="M")
				rep_handle.content = open(temp_filename)
				rep_handle.label = "{label}_PREVIEW".format(label=ds['label'])
				rep_handle.save()

				# thumbnail				
				im = Image.open(temp_filename)	
				width, height = im.size
				max_width = 200	
				max_height = 200
				im.thumbnail((max_width, max_height), Image.ANTIALIAS)		
				im.save(temp_filename,"JPEG")
				rep_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "{ds_id}_THUMBNAIL".format(ds_id=ds['ds_id']), "{label}_THUMBNAIL".format(label=ds['label']), mimetype="image/jpeg", control_group="M")
				rep_handle.content = open(temp_filename)
				rep_handle.label = "{label}_THUMBNAIL".format(label=ds['label'])
				rep_handle.save()				
				
				# remove temp waveform
				os.system('rm {temp_filename}'.format(temp_filename=temp_filename))

				# append to playlist_list
				playlist_list.append(ds)
				

			# write PLAYLIST datastream with playlist_list
			print "Generating PLAYLIST datastream"
			for ds in playlist_list:
				ds['thumbnail'] = "http://{APP_HOST}/fedora/objects/{pid}/datastreams/{ds_id}_THUMBNAIL/content".format(pid=self.ohandle.pid,ds_id=ds['ds_id'],APP_HOST=localConfig.APP_HOST)
				ds['preview'] = "http://{APP_HOST}/fedora/objects/{pid}/datastreams/{ds_id}_PREVIEW/content".format(pid=self.ohandle.pid,ds_id=ds['ds_id'],APP_HOST=localConfig.APP_HOST)
				ds['mp3'] = "http://{APP_HOST}/fedora/objects/{pid}/datastreams/{ds_id}_MP3/content".format(pid=self.ohandle.pid,ds_id=ds['ds_id'],APP_HOST=localConfig.APP_HOST)
				ds['steaming_mp3'] = "http://{APP_HOST}/fedora/objects/{pid}/datastreams/{ds_id}_MP3/content".format(pid=self.ohandle.pid,ds_id=ds['ds_id'],APP_HOST=localConfig.APP_HOST)

			playlist_handle = eulfedora.models.DatastreamObject(self.ohandle,"PLAYLIST", "PLAYLIST", mimetype="application/json", control_group="M")
			playlist_handle.content = json.dumps( sorted(playlist_list, key=lambda k: k['order']) )
			playlist_handle.label = "PLAYLIST"
			playlist_handle.save()


			# write generic thumbnail and preview for object
			for gen_type in ['THUMBNAIL','PREVIEW']:
				rep_handle = eulfedora.models.DatastreamObject(self.ohandle,gen_type, gen_type, mimetype="image/jpeg", control_group="M")
				rep_handle.ds_location = "http://{APP_HOST}/fedora/objects/{pid}/datastreams/{ds_id}_{gen_type}/content".format(pid=self.ohandle.pid,ds_id=self.objMeta['isRepresentedBy'],gen_type=gen_type,APP_HOST=localConfig.APP_HOST)
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



























