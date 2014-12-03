#!/usr/bin/env python
# -*- coding: utf-8 -*-

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
import StringIO
import tarfile

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

			# check if payload actual eulfedora object or string literal, in latter case, attempt to open eul object
			if type(payload) != eulfedora.models.DigitalObject:
				payload = fedora_handle.get_object(payload)

			if payload.exists == False:
				print "Object does not exist, cannot instantiate as WSUDOR type object."
				return False
			
			# GET object content_model
			# Using prefix "WSUDOR_" for v2, consider adding this to RELS for all objects!?
			content_type = payload.risearch.get_objects(payload.uri,'info:fedora/fedora-system:def/relations-external#hasContentModel')
			content_type = content_type.next().split(":")[-1]			
			content_type = "WSUDOR_"+str(content_type)
		
		print "Our content type is:",content_type

	except Exception,e:
		print traceback.format_exc()
		print e
		return False
	
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
				"external_relationships":[
					"http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isDiscoverable",
					"http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/hasSecurityPolicy"					
				]
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

				# instantiate bag propoerties
				self.pid = self.objMeta['id']
				self.label = self.objMeta['label']
				self.content_type = content_type # use content_type as derived from WSUDOR_Object factory

				# placeholder for future ohandle
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
				if type(payload) != eulfedora.models.DigitalObject:
					payload = fedora_handle.get_object(payload)

				# instantiate WSUDOR propoerties
				self.object_type = object_type
				self.pid = payload.pid
				self.pid_suffix = payload.pid.split(":")[1]
				self.content_type = content_type
				self.ohandle = payload
				self.objMeta = json.loads(self.ohandle.getDatastreamObject('OBJMETA').content)


		except Exception,e:
			print traceback.format_exc()
			print e


	# function that runs at end of ContentType ingestBag(), running ingest processes generic to ALL objects
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


	def exportBag(self,job_package):

		'''
		Target Example:
		.
		├── bag-info.txt
		├── bagit.txt
		├── data
		│   ├── datastreams
		│   │   ├── roots.jpg
		│   │   └── trunk.jpg
		│   ├── MODS.xml
		│   └── objMeta.json
		├── manifest-md5.txt
		└── tagmanifest-md5.txt

		Consider extending this to ContentTypes if becomes to complex for genObjects...
		'''
		
		# get PID
		PID = self.pid
		form_data = job_package['form_data']

		# create temp dir structure
		working_dir = "/tmp/Ouroboros/export_bags"
		temp_dir = working_dir + "/" + str(uuid.uuid4())
		os.system("mkdir {temp_dir}".format(temp_dir=temp_dir))
		os.system("mkdir {temp_dir}/data".format(temp_dir=temp_dir))
		os.system("mkdir {temp_dir}/data/datastreams".format(temp_dir=temp_dir))

		# move bagit files to temp dir, and unpack
		bagit_files = self.ohandle.getDatastreamObject("BAGIT_META").content
		bagitIO = StringIO.StringIO(bagit_files)
		tar_handle = tarfile.open(fileobj=bagitIO)
		tar_handle.extractall(path=temp_dir)
		
		'''
		This section might become much more complex - might need handlers for different mimetypes?
		*This would support delegating exportObjects() to the ContentType*
		'''
		
		# export datastreams based on DS ids and objMeta / requires (ds_id,full path filename) tuples to write them
		def writeDS(write_tuple):
			print "WORKING ON {ds_id}".format(ds_id=write_tuple[0])

			ds_handle = self.ohandle.getDatastreamObject(write_tuple[0])
			fhand = open(write_tuple[1],'w')

			# XML ds model
			if isinstance(ds_handle,eulfedora.models.XmlDatastreamObject):
				print "FIRING XML"
				fhand.write(ds_handle.content.serialize())
				fhand.close() 

			# generic ds model (isinstance(ds_handle,eulfedora.models.DatastreamObject))
			else:
				print "FIRING GENERIC"
				fhand.write(ds_handle.content)
				fhand.close()


		# write original datastreams
		for ds in self.objMeta['datastreams']:
			writeDS((ds['ds_id'],"{temp_dir}/data/datastreams/{filename}".format(temp_dir=temp_dir, filename=ds['filename'])))


		# write MODS and objMeta files
		simple = [
			("MODS","{temp_dir}/data/MODS.xml".format(temp_dir=temp_dir)),
			("OBJMETA","{temp_dir}/data/objMeta.json".format(temp_dir=temp_dir))
		]
		for ds in simple:
			writeDS(ds)

		# tarball it up
		named_dir = self.pid.replace(":","-")
		os.system("mv {temp_dir} {working_dir}/{named_dir}".format(temp_dir=temp_dir, working_dir=working_dir, named_dir=named_dir))
		os.chdir(working_dir)
		os.system("tar -cvf {named_dir}.tar {named_dir}".format(working_dir=working_dir, named_dir=named_dir))
		os.system("rm -r {working_dir}/{named_dir}".format(working_dir=working_dir, named_dir=named_dir))

		# move to web accessible location, with username as folder
		username = job_package['username']
		target_dir = "/var/www/wsuls/Ouroboros/export/{username}".format(username=username)
		if os.path.exists(target_dir) == False:
			os.system("mkdir {target_dir}".format(target_dir=target_dir))
		os.system("mv {named_dir}.tar {target_dir}".format(named_dir=named_dir,target_dir=target_dir))

		return "http://digital.library.wayne.edu/Ouroboros/export/{username}/{named_dir}.tar".format(named_dir=named_dir,username=username)


	# derive DC from MODS (experimental action in Gen ContentType)	
	def DCfromMODS(self):
		'''
		Experimental - needs celery processing
		'''
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






































	


