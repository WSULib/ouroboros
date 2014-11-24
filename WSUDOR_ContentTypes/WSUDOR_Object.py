# module for management of bags in the WSUDOR environment
import bagit
import os
import mimetypes
import json
import traceback
import sys
from lxml import etree
import tarfile
import uuid

# celery
from cl.cl import celery

# eulfedora
import eulfedora

# handles
from WSUDOR_Manager.solrHandles import solr_handle
from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager import redisHandles


import WSUDOR_ContentTypes


# class factory, returns WSUDOR_GenObject as extended by specific ContentType
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



# WSUDOR Generic Object class (designed to be extended by ContentTypes)
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

				# placeholder for potential ohandle
				self.ohandle = None

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


	# function that runs at end of ContentType ingestBag(), pulling in generic BagIt metadata to made object
	def finishIngest(self):

		# as object finishes ingest, it can be granted eulfedora methods, its 'ohandle' attribute
		if self.ohandle != None:
			self.ohandle = fedora_handle.get_object(self.objMeta['id'])

		# pull in BagIt metadata as BAG_META datastream tarball
		temp_filename = "/tmp/Ouroboros/"+str(uuid.uuid4())+".tar"
		tar_handle = tarfile.open(temp_filename,'w')
		for bag_meta_file in ['bag-info.txt','bagit.txt','manifest-md5.txt','tagmanifest-md5.txt']:
			tar_handle.add(self.Bag.path + "/" + bag_meta_file, recursive=False, arcname=bag_meta_file)
		tar_handle.close()
		bag_meta_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "BAGIT_META", "BagIt Metadata Tarball", mimetype="application/x-tar", control_group='M')
		bag_meta_handle.label = "BagIt Metadata Tarball"
		bag_meta_handle.content = open(temp_filename)
		bag_meta_handle.save()
		os.system('rm {temp_filename}'.format(temp_filename=temp_filename))		

		# derive Dublin Core from MODS, update DC datastream
		self.DCfromMODS()
		
		# finally, return
		return True


	# derive DC from MODS (experimental action in Gen ContentType)
	def DCfromMODS(self):
		# retrieve MODS		
		MODS_handle = self.ohandle.getDatastreamObject('MODS')		
		XMLroot = etree.fromstring(MODS_handle.content.serialize())

		# 2) transform downloaded MODS to DC with LOC stylesheet
		print "XSLT Transforming: {PID}".format(PID=self.pid)
		# Saxon transformation
		XSLhand = open('inc/xsl/MODS_to_DC.xsl','r')		
		xslt_tree = etree.parse(XSLhand)
		transform = etree.XSLT(xslt_tree)
		DC = transform(XMLroot)		

		# 3) save to DC datastream
		DS_handle = self.ohandle.getDatastreamObject("DC")
		DS_handle.content = str(DC)
		derive_results = DS_handle.save()
		print "DCfromMODS result:",derive_results
		return derive_results






































	


