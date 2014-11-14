# module for management of bags in the WSUDOR environment
import bagit
import os
import mimetypes
import json
import traceback
import sys

# celery
from cl.cl import celery

# eulfedora
import eulfedora

# handles
from WSUDOR_Manager.solrHandles import solr_handle
from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager import redisHandles

# import WSUDOR_ContentTypes
import WSUDOR_ContentTypes


class WSUDOR_Object:

	'''
	This class represents an object already present, or destined, for Ouroboros.  
	"objType" is required for discerning between the two.

	objType = 'WSUDOR'
		- object is present in WSUDOR, actions include management and export

	objType = 'bag'
		- object is present outside of WSUDOR, actions include primarily ingest and validation
	'''

	# init
	def __init__(self,objType=False,bag_dir=False,eulfedoraObject=False):
		
		
		if objType == "bag":
			self.objType = objType
			try:
				# read objMeta.json
				path = bag_dir + '/data/objMeta.json'
				fhand = open(path,'r')
				self.objMeta = json.loads(fhand.read())
				print "objMeta.json loaded for:",self.objMeta['id'],"/",self.objMeta['label']

				self.pid = self.objMeta['id']
				self.label = self.objMeta['label']
				self.content_type = self.objMeta['content_type']

				# BagIt methods
				self.Bag = bagit.Bag(bag_dir)

				# validate object, log to "error_dict" attribute if invalid
				try:
					self.Bag.validate()
				except Exception,e:
					print traceback.format_exc()
					print e.message
					error_dict = {
						"traceback":traceback.format_exc(),
						"error_message":e.message,
						"error_details":e.details
					}
					self.instantiateError = error_dict					
			
			except Exception,e:
				print traceback.format_exc()
				print e

		if objType == "WSUDOR":
			self.objType = objType
			self.pid = eulfedoraObject.pid
			self.pid_suffix = eulfedoraObject.pid.split(":")[1]
			self.ohandle = eulfedoraObject

			# GET object content_model
			# Using prefix "WSUDOR_" for v2, consider adding this to RELS for all objects!?
			content_type = self.ohandle.risearch.get_objects(self.ohandle.uri,'info:fedora/fedora-system:def/relations-external#hasContentModel')
			content_type = content_type.next().split(":")[-1]			
			self.content_type = "WSUDOR_"+str(content_type)

			
		# Retrieve ContentType specifics
		self.ContentType = getattr(WSUDOR_ContentTypes,self.content_type)(self)		


	









