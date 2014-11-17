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


import WSUDOR_ContentTypes


def WSUDOR_Object(object_type,payload):

	'''	
	Function to determine ContentType, then fire the appropriate subclass to WSUDOR_GenObject
	'''

	try:
		# Future WSUDOR object, BagIt object
		if object_type == "bag":		
			# read objMeta.json
			path = payload + '/data/objMeta.json'
			fhand = open(path,'r')
			objMeta = json.loads(fhand.read())
			# only need content_type
			content_type = objMeta['content_type']		
			
		
		# Active, WSUDOR object
		if object_type == "WSUDOR":

			# check if payload actual eulfedora object or string literal
			# in latter case, attempt to open eul object
			if type(payload) != eulfedora.models.DigitalObject:
				payload = fedora_handle.get_object(payload)
			
			# GET object content_model
			# Using prefix "WSUDOR_" for v2, consider adding this to RELS for all objects!?
			content_type = payload.risearch.get_objects(payload.uri,'info:fedora/fedora-system:def/relations-external#hasContentModel')
			content_type = content_type.next().split(":")[-1]			
			content_type = "WSUDOR_"+str(content_type)

		
		print "Our content type is:",content_type

	except Exception,e:
		print traceback.format_exc()
		print e
		return "Could not load WSUDOR or Bag object."
	
	# need check if valid subclass of WSUDOR_GenObject	
	return getattr(WSUDOR_ContentTypes,str(content_type))(object_type=object_type,content_type=content_type,payload=payload)



# WSUDOR Generic Object class (meant to be extended by ContentTypes)
class WSUDOR_GenObject(object):

	'''
	This class represents an object already present, or destined, for Ouroboros.  
	"object_type" is required for discerning between the two.

	object_type = 'WSUDOR'
		- object is present in WSUDOR, actions include management and export

	object_type = 'bag'
		- object is present outside of WSUDOR, actions include primarily ingest and validation
	'''	

	# ContentType rquirements dictionary
	# initialized here, added to by sub-classes		

	# init
	def __init__(self,object_type=False,content_type=False,payload=False):	

		self.struct_requirements = {
			"WSUDOR_GenObject":{
				"datastreams":[
					{
						"id":"THUMBNAIL",
						"purpose":"Thumbnail of image",
						"mimetype":"image/jpeg"
					},
					{
						"id":"PREVIEW",
						"purpose":"Medium sized preview image",
						"mimetype":"image/jpeg"
					},			
					{
						"id":"MODS",
						"purpose":"Descriptive MODS",
						"mimetype":"text/xml"
					},
					{
						"id":"RELS-EXT",
						"purpose":"RDF relationships",
						"mimetype":"application/rdf+xml"
					},
					{
						"id":"POLICY",
						"purpose":"XACML Policy",
						"mimetype":"text/xml"
					}
				],
				"external_relationships":[]
			}		
		}	

		try:			

			# Future WSUDOR object, BagIt object
			if object_type == "bag":
				self.object_type = object_type

				# read objMeta.json
				path = payload + '/data/objMeta.json'
				fhand = open(path,'r')
				self.objMeta = json.loads(fhand.read())
				print "objMeta.json loaded for:",self.objMeta['id'],"/",self.objMeta['label']

				self.pid = self.objMeta['id']
				self.label = self.objMeta['label']
				self.content_type = content_type # use content_type as derived from WSUDOR_Object factory

				# BagIt methods
				self.Bag = bagit.Bag(payload)

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


				# load also, WSUDOR object handle

				# # check if payload actual eulfedora object or string literal
				# # in latter case, attempt to open eul object
				# if type(payload) != eulfedora.models.DigitalObject:
				# 	payload = fedora_handle.get_object(payload)
				# self.ohandle = payload
				

			# Active, WSUDOR object
			if object_type == "WSUDOR":

				# check if payload actual eulfedora object or string literal
				# in latter case, attempt to open eul object
				if type(payload) != eulfedora.models.DigitalObject:
					payload = fedora_handle.get_object(payload)

				self.object_type = object_type
				self.pid = payload.pid
				self.pid_suffix = payload.pid.split(":")[1]
				self.ohandle = payload
				self.content_type = content_type

		except Exception,e:
			print traceback.format_exc()
			print e


	


