# -*- coding: utf-8 -*-

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
import xmltodict
from lxml import etree
import requests
import time
import ast

# library for working with LOC BagIt standard 
import bagit

# celery
from cl.cl import celery

# eulfedora
import eulfedora

# WSUDOR
import WSUDOR_ContentTypes
from WSUDOR_Manager.solrHandles import solr_handle, solr_manage_handle
from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager import models, helpers, redisHandles, actions, utilities



# class factory, returns WSUDOR_GenObject as extended by specific ContentType
def WSUDOR_Object(payload, object_type="WSUDOR"):

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
			
			# GET WSUDOR_X object content_model
			'''
			This is an important pivot.  We're taking the old ContentModel syntax: "info:fedora/CM:Image", and slicing only the last component off 
			to use, "Image".  Then, we append that to "WSUDOR_" to get ContentTypes such as "WSUDOR_Image", or "WSUDOR_Collection", etc.
			'''
			try:
				content_types = list(payload.risearch.get_objects(payload.uri,'info:fedora/fedora-system:def/relations-external#hasContentModel'))
				if len(content_types) <= 1:
					content_type = content_types[0].split(":")[-1]
				else:
					try:
						# use preferredContentModel relationship to disambiguate
						pref_type = list(payload.risearch.get_objects(payload.uri,'http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/preferredContentModel'))
						pref_type = pref_type[0].split(":")[-1]
						content_type = pref_type
					except:
						print "More than one hasContentModel found, but no preferredContentModel.  Aborting."
						return False

				content_type = "WSUDOR_"+str(content_type)

			# fallback, grab straight from OBJMETA datastream / only fires for v2 objects
			except:				
				if "OBJMETA" in payload.ds_list:
					print "Race conditions detected, grabbing content_type from objMeta"
					objmeta = json.loads(payload.getDatastreamObject('OBJMETA').content)
					content_type = objmeta['content_type']

		print "Our content type is:",content_type

	except Exception,e:
		print traceback.format_exc()
		print e
		return False
	
	# need check if valid subclass of WSUDOR_GenObject	
	try:
		return getattr(WSUDOR_ContentTypes, str(content_type))(object_type = object_type, content_type = content_type, payload = payload)	
	except:
		print "Could not find appropriate ContentType, returning False."		
		return False





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
	############################################################################################################
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

		# two roads - WSUDOR or BagIt archive for the object returned
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
				# only fires for v2 objects
				if "OBJMETA" in self.ohandle.ds_list:
					self.objMeta = json.loads(self.ohandle.getDatastreamObject('OBJMETA').content)			


		except Exception,e:
			print traceback.format_exc()
			print e



	# Lazy Loaded properties
	############################################################################################################
	'''
	These properties use helpers.LazyProperty decorator, to avoid loading them if not called.
	'''
	
	# MODS metadata
	@helpers.LazyProperty
	def MODS_XML(self):
		return self.ohandle.getDatastreamObject('MODS').content.serialize()

	@helpers.LazyProperty
	def MODS_dict(self):
		return xmltodict.parse(self.MODS_XML)

	@helpers.LazyProperty
	def MODS_Solr_flat(self):
		# flattens MODS with GSearch XSLT and loads as dictionary
		XSLhand = open('inc/xsl/MODS_extract.xsl','r')		
		xslt_tree = etree.parse(XSLhand)
  		transform = etree.XSLT(xslt_tree)
  		XMLroot = etree.fromstring(self.MODS_XML)
		SolrXML = transform(XMLroot)
		return xmltodict.parse(str(SolrXML))
	
	#DC metadata
	@helpers.LazyProperty
	def DC_XML(self):
		return self.ohandle.getDatastreamObject('DC').content.serialize()

	@helpers.LazyProperty
	def DC_dict(self):
		return xmltodict.parse(self.DC_XML)

	@helpers.LazyProperty
	def DC_Solr_flat(self):
		# flattens MODS with GSearch XSLT and loads as dictionary
		XSLhand = open('inc/xsl/DC_extract.xsl','r')		
		xslt_tree = etree.parse(XSLhand)
  		transform = etree.XSLT(xslt_tree)
  		XMLroot = etree.fromstring(self.DC_XML)
		SolrXML = transform(XMLroot)
		return xmltodict.parse(str(SolrXML))

	#RELS-EXT and RELS-INT metadata
	@helpers.LazyProperty
	def RELS_EXT_Solr_flat(self):
		# flattens MODS with GSearch XSLT and loads as dictionary
		XSLhand = open('inc/xsl/RELS-EXT_extract.xsl','r')		
		xslt_tree = etree.parse(XSLhand)
  		transform = etree.XSLT(xslt_tree)
  		# raw, unmodified RDF
  		raw_xml_URL = "http://localhost/fedora/objects/{PID}/datastreams/RELS-EXT/content".format(PID=self.pid)
  		raw_xml = requests.get(raw_xml_URL).text.encode("utf-8")
  		XMLroot = etree.fromstring(raw_xml)
		SolrXML = transform(XMLroot)
		return xmltodict.parse(str(SolrXML))

	@helpers.LazyProperty
	def RELS_INT_Solr_flat(self):
		# flattens MODS with GSearch XSLT and loads as dictionary
		XSLhand = open('inc/xsl/RELS-EXT_extract.xsl','r')		
		xslt_tree = etree.parse(XSLhand)
  		transform = etree.XSLT(xslt_tree)
  		# raw, unmodified RDF
  		raw_xml_URL = "http://localhost/fedora/objects/{PID}/datastreams/RELS-INT/content".format(PID=self.pid)
  		raw_xml = requests.get(raw_xml_URL).text.encode("utf-8")
  		XMLroot = etree.fromstring(raw_xml)
		SolrXML = transform(XMLroot)
		return xmltodict.parse(str(SolrXML))


	# SolrDoc class
	@helpers.LazyProperty
	def SolrDoc(self):
		return models.SolrDoc(self.pid)


	# SolrSearchDoc class
	@helpers.LazyProperty
	def SolrSearchDoc(self):
		return models.SolrSearchDoc(self.pid)


	@helpers.LazyProperty
	def objSizeDict(self):

		'''
		Begin storing in Redis.
		If not stored, generate and store.
		If stored, return.
		'''

		# check Redis for object size dictionary
		r_response = redisHandles.r_catchall.get(self.pid)
		if r_response != None:
			print "object size dictionary located and retrieved from Redis"
			return ast.literal_eval(r_response)

		else:
			print "generating object size dictionary, storing in redis, returning"

			size_dict = {}
			tot_size = 0

			# loop through datastreams, append size to return dictionary
			for ds in self.ohandle.ds_list:
				ds_handle = self.ohandle.getDatastreamObject(ds)
				ds_size = ds_handle.size
				tot_size += ds_size
				size_dict[ds] = ( ds_size, utilities.sizeof_fmt(ds_size) )

			size_dict['total_size'] = (tot_size, utilities.sizeof_fmt(tot_size) )

			# store in Redis
			redisHandles.r_catchall.set(self.pid, size_dict)

			# return 
			return size_dict			
			



		



	# WSUDOR_Object Methods
	############################################################################################################
	# function that runs at end of ContentType ingestBag(), running ingest processes generic to ALL objects
	def finishIngest(self, gen_manifest=False):

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

		# Write isWSUDORObject RELS-EXT relationship
		self.ohandle.add_relationship("http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isWSUDORObject","True")

		# generate OAI identifier
		print self.ohandle.add_relationship("http://www.openarchives.org/OAI/2.0/itemID", "oai:digital.library.wayne.edu:{PID}".format(PID=self.pid))

		# affiliate with collection set
		try:
			collections = self.previewSolrDict()['rels_isMemberOfCollection']
			for collection in collections:			
				print self.ohandle.add_relationship("http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isMemberOfOAISet", collection)
		except:
			print "could not affiliate with collection"

		# Index in Solr
		self.indexToSolr()

		# if gen_manifest set, generate IIIF Manifest
		if gen_manifest == True:
			self.genIIIFManifest()

		# finally, return
		return True


	def exportBag(self, job_package=False, returnTargetDir=False, includeRELS=False):

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

		# create temp dir structure
		working_dir = "/tmp/Ouroboros/export_bags"
		temp_dir = working_dir + "/" + str(uuid.uuid4())
		time.sleep(.25)
		os.system("mkdir {temp_dir}".format(temp_dir=temp_dir))
		time.sleep(.25)
		os.system("mkdir {temp_dir}/data".format(temp_dir=temp_dir))
		time.sleep(.25)
		os.system("mkdir {temp_dir}/data/datastreams".format(temp_dir=temp_dir))

		# move bagit files to temp dir, and unpack
		bagit_files = self.ohandle.getDatastreamObject("BAGIT_META").content
		bagitIO = StringIO.StringIO(bagit_files)
		tar_handle = tarfile.open(fileobj=bagitIO)
		tar_handle.extractall(path=temp_dir)		
		
		# export datastreams based on DS ids and objMeta / requires (ds_id,full path filename) tuples to write them
		def writeDS(write_tuple):
			print "WORKING ON {ds_id}".format(ds_id=write_tuple[0])

			ds_handle = self.ohandle.getDatastreamObject(write_tuple[0])
			fhand = open(write_tuple[1],'w')

			# XML ds model
			if isinstance(ds_handle,eulfedora.models.XmlDatastreamObject):
				print "FIRING XML WRITER"
				fhand.write(ds_handle.content.serialize())
				fhand.close() 

			# generic ds model (isinstance(ds_handle,eulfedora.models.DatastreamObject))
			else:
				print "FIRING GENERIC WRITER"
				fhand.write(ds_handle.content)
				fhand.close()


		# write original datastreams
		for ds in self.objMeta['datastreams']:
			writeDS((ds['ds_id'],"{temp_dir}/data/datastreams/{filename}".format(temp_dir=temp_dir, filename=ds['filename'])))


		# include RELS
		if includeRELS == True:
			for ds in ['RELS-EXT','RELS-INT']:
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
		orig_dir = os.getcwd()
		os.chdir(working_dir)
		os.system("tar -cvf {named_dir}.tar {named_dir}".format(working_dir=working_dir, named_dir=named_dir))
		os.system("rm -r {working_dir}/{named_dir}".format(working_dir=working_dir, named_dir=named_dir))

		# move to web accessible location, with username as folder
		if job_package != False:
			username = job_package['username']
		else:
			username = "consoleUser"
		target_dir = "/var/www/wsuls/Ouroboros/export/{username}".format(username=username)
		if os.path.exists(target_dir) == False:
			os.system("mkdir {target_dir}".format(target_dir=target_dir))
		os.system("mv {named_dir}.tar {target_dir}".format(named_dir=named_dir,target_dir=target_dir))

		# jump back to origina working dir
		os.chdir(orig_dir)

		if returnTargetDir == True:
			return "{target_dir}/{named_dir}.tar".format(target_dir=target_dir,named_dir=named_dir)
		else:
			return "http://digital.library.wayne.edu/Ouroboros/export/{username}/{named_dir}.tar".format(named_dir=named_dir,username=username)


	# reingest bag
	def reingestBag(self, removeExportTar = False):
		
		# get PID
		PID = self.pid

		print "Roundrip Ingesting:",PID

		# export bag, returning the file structure location of tar file
		export_tar = self.exportBag(returnTargetDir=True)
		print "Location of export tar file:",export_tar

		# purge self
		fedora_handle.purge_object(PID)

		# reingest exported tar file
		actions.bagIngest.ingestBag(actions.bagIngest.payloadExtractor(export_tar,'single'))

		# delete exported tar
		if removeExportTar == True:
			print "Removing export tar..."
			os.remove(export_tar)

		# return 
		return PID,"Reingested."



	# Solr Indexing
	def indexToSolr(self, printOnly=False):
		return actions.solrIndexer.solrIndexer('modifyObject', self.pid, printOnly)


	def previewSolrDict(self):
		'''
		Function to run current WSUDOR object through indexSolr() transforms
		'''
		try:
			return actions.solrIndexer.solrIndexer('modifyObject', self.pid, printOnly=True)
		except:
			print "Could not run indexSolr() transform."
			return False


	################################################################
	# Consider moving
	################################################################
	# derive DC from MODS
	def DCfromMODS(self):
		
		# 1) retrieve MODS		
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



	


