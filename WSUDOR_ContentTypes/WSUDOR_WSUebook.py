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
from WSUDOR_Manager import redisHandles, helpers, utilities


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

		# check that content_type is a valid ContentType				
		if self.__class__ not in WSUDOR_ContentTypes.WSUDOR_GenObject.__subclasses__():
			report_failure(("Valid ContentType","WSUDOR_Object instance's ContentType: {content_type}, not found in acceptable ContentTypes: {ContentTypes_list} ".format(content_type=self.content_type,ContentTypes_list=WSUDOR_ContentTypes.WSUDOR_GenObject.__subclasses__())))				
		
		
		# finally, return verdict
		return results_dict


	# ingest 
	def ingestBag(self):
		pass


	# complex size determination, overrides WSUDOR_Generic
	@helpers.LazyProperty
	def objSizeDict(self):

		print "Determining size of WSUDOR_WSUebook object"

		size_dict = {}
		tot_size = 0

		# loop through datastreams, append size to return dictionary
		for ds in self.ohandle.ds_list:
			ds_handle = self.ohandle.getDatastreamObject(ds)
			ds_size = ds_handle.size
			tot_size += ds_size
			size_dict[ds] = ( ds_size, utilities.sizeof_fmt(ds_size) )

		# get constituents and determine total size		
		riquery = fedora_handle.risearch.get_subjects(predicate="info:fedora/fedora-system:def/relations-external#isMemberOf", object=self.ohandle.uri)
		members = list(riquery)		

		for PID in members:

			print "Working on",PID
			
			loop_ohandle = fedora_handle.get_object(PID)

			loop_size_dict = {}
			loop_tot_size = 0

			# loop through datastreams, append size to return dictionary
			for ds in loop_ohandle.ds_list:
				ds_handle = loop_ohandle.getDatastreamObject(ds)
				ds_size = ds_handle.size
				loop_tot_size += ds_size
				
				# holding off for now - would be thousdands of lines long
				# loop_size_dict[ds] = ( ds_size, utilities.sizeof_fmt(ds_size) )

			size_dict["isMemberOf_"+PID] = ( loop_tot_size, utilities.sizeof_fmt(loop_tot_size) )
			tot_size += loop_tot_size

		size_dict['total_size'] = (tot_size, utilities.sizeof_fmt(tot_size) )
		print size_dict

		return size_dict


























