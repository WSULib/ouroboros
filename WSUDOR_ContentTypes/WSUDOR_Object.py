# module for management of bags in the WSUDOR environment
import bagit
import os
import mimetypes
import json

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


		if objType == "WSUDOR":
			self.pid = eulfedoraObject.pid
			self.pid_suffix = eulfedoraObject.pid.split(":")[1]
			self.ohandle = eulfedoraObject

			# GET object content_model
			# Using prefix "WSUDOR_" for v2, consider adding this to RELS for all objects!?
			self.content_type = None

			#######################################
			# MOVE TO SOMEWHERE CENTRAL		
			#######################################
			# import WSUDOR opinionated mimes
			opinionated_mimes = {
				# images
				"image/jp2":".jp2"		
			}	

			# push to mimetypes.types_map
			for k, v in opinionated_mimes.items():
				# reversed here
				mimetypes.types_map[v] = k
			#######################################


		# Retrieve ContentType specifics
		self.ContentType = getattr(WSUDOR_ContentTypes,self.content_type)(self)		


	









