#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import mimetypes
import json
import uuid
import Image
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
from WSUDOR_Manager import redisHandles


class WSUDOR_WSUebook(WSUDOR_ContentTypes.WSUDOR_GenObject):

	def __init__(self,object_type=False,content_type=False,payload=False):
		
		# run __init__ from parent class
		WSUDOR_ContentTypes.WSUDOR_GenObject.__init__(self,object_type, content_type, payload)
		
		# Add WSUDOR_Image struct_requirements to WSUDOR_Object instance struct_requirements
		self.struct_requirements['WSUDOR_WSUebook'] = {
			"datastreams":[
				{
					"id":"DUMMY_TEXT",
					"purpose":"DUMMY_TEXT",
					"mimetype":"DUMMY_TEXT"
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
		# ds_ids = [each['ds_id'] for each in self.objMeta['datastreams']]
		# if self.objMeta['isRepresentedBy'] not in ds_ids:
		# 	report_failure(("isRepresentedBy_check","{isRep} is not in {ds_ids}".format(isRep=self.objMeta['isRepresentedBy'],ds_ids=ds_ids)))


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


	# ingest 
	def ingestBag(self):
		pass


























