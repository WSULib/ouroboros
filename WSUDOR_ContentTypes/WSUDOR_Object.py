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
import zipfile
import shutil
import ConfigParser
import glob
import hashlib
from urllib import unquote, quote_plus, urlopen
from collections import deque
import struct
from PIL import Image

# library for working with LOC BagIt standard
import bagit

# celery
from WSUDOR_Manager import celery

# eulfedora
import eulfedora
from eulfedora import syncutil

# localConfig
import localConfig

# WSUDOR
import WSUDOR_ContentTypes
from WSUDOR_Manager.solrHandles import solr_handle
from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager import fedoraHandles
from WSUDOR_Manager import models, helpers, redisHandles, actions, utilities

# derivatives
from inc.derivatives import JP2DerivativeMaker

# jpylyzer
from jpylyzer import jpylyzer
from jpylyzer import etpatch



# class factory, returns WSUDOR_GenObject as extended by specific ContentType
def WSUDOR_Object(payload, orig_payload=False, object_type="WSUDOR"):

	'''
	Function to determine ContentType, then fire the appropriate subclass to WSUDOR_GenObject
	'''

	try:
		# Future WSUDOR object, BagIt object
		if object_type == "bag":

			# prepare new working dir & recall original
			working_dir = "/tmp/Ouroboros/"+str(uuid.uuid4())
			print "object_type is bag, creating working dir at", working_dir
			orig_payload = payload

			'''
			# determine if directory or archive file
			# if dir, copy to, if archive, decompress and copy
			# set 'working_dir' to new location in /tmp/Ouroboros
			'''
			if os.path.isdir(payload):
				print "directory detected, symlinking"
				# shutil.copytree(payload,working_dir)
				os.symlink(payload, working_dir)


			# tar file or gz
			elif payload.endswith(('.tar','.gz')):
				print "tar / gz detected, decompressing"
				tar_handle = tarfile.open(payload,'r')
				tar_handle.extractall(path=working_dir)
				payload = working_dir

			elif payload.endswith('zip'):
				print "zip file detected, unzipping"
				with zipfile.ZipFile(payload, 'r') as z:
					z.extractall(working_dir)

			# if the working dir has a sub-dir, assume that's the object directory proper
			if len(os.listdir(working_dir)) == 1 and os.path.isdir("/".join((working_dir, os.listdir(working_dir)[0]))):
				print "we got a sub-dir"
				payload = "/".join((working_dir,os.listdir(working_dir)[0]))
			else:
				payload = working_dir
			print "payload is:",payload

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
		return getattr(WSUDOR_ContentTypes, str(content_type))(object_type = object_type, content_type = content_type, payload = payload, orig_payload = orig_payload)
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
	def __init__(self, object_type=False, content_type=False, payload=False, orig_payload=False):

		self.index_on_ingest = True,
		self.struct_requirements = {
			"WSUDOR_GenObject":{
				"datastreams":[
					{
						"id":"THUMBNAIL",
						"purpose":"Thumbnail of image",
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
		self.orig_payload = orig_payload

		# WSUDOR or BagIt archive for the object returned
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
				self.temp_payload = self.Bag.path


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
		raw_xml_URL = "http://localhost/fedora/objects/%s/datastreams/RELS-EXT/content" % (self.pid)
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
		raw_xml_URL = "http://localhost/fedora/objects/%s/datastreams/RELS-INT/content" % (self.pid)
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


	# return IIIF maniest
	@helpers.LazyProperty
	def iiif_manifest(self):
		return json.loads(redisHandles.r_iiif.get(self.pid))


	@helpers.LazyProperty
	def objSizeDict(self):

		'''
		Begin storing in Redis.
		If not stored, generate and store.
		If stored, return.

		Improvement: need to provide method for updating
		'''

		# check Redis for object size dictionary
		r_response = redisHandles.r_catchall.get(self.pid)
		if r_response != None and not update:
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


	def update_objSizeDict(self):

		# clear from Redis
		print "clearing previous entry in Redis"
		redisHandles.r_catchall.delete(self.pid)

		print "regenerating and returning"
		return self.objSizeDict




	# WSUDOR_Object Methods
	############################################################################################################
	# generic, simple ingest
	def ingestBag(self, indexObject=True):
		if self.object_type != "bag":
			raise Exception("WSUDOR_Object instance is not 'bag' type, aborting.")

		# ingest Volume object
		try:
			self.ohandle = fedora_handle.get_object(self.objMeta['id'],create=True)
			self.ohandle.save()

			# set base properties of object
			self.ohandle.label = self.objMeta['label']

			# write POLICY datastream (NOTE: 'E' management type required, not 'R')
			print "Using policy:",self.objMeta['policy']
			policy_suffix = self.objMeta['policy']
			policy_handle = eulfedora.models.DatastreamObject(self.ohandle,"POLICY", "POLICY", mimetype="text/xml", control_group="E")
			policy_handle.ds_location = "http://localhost/fedora/objects/%s/datastreams/POLICY_XML/content" % (policy_suffix)
			policy_handle.label = "POLICY"
			policy_handle.save()

			# write objMeta as datastream
			objMeta_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "OBJMETA", "Ingest Bag Object Metadata", mimetype="application/json", control_group='M')
			objMeta_handle.label = "Ingest Bag Object Metadata"
			objMeta_handle.content = json.dumps(self.objMeta)
			objMeta_handle.save()

			# write explicit RELS-EXT relationships
			for relationship in self.objMeta['object_relationships']:
				print "Writing relationship:",str(relationship['predicate']),str(relationship['object'])
				self.ohandle.add_relationship(str(relationship['predicate']),str(relationship['object']))

			# writes derived RELS-EXT
			content_type_string = "info:fedora/CM:"+self.objMeta['content_type'].split("_")[1]
			self.ohandle.add_relationship("info:fedora/fedora-system:def/relations-external#hasContentModel",content_type_string)

			# write MODS datastream if MODS.xml exists
			if os.path.exists(self.Bag.path + "/data/MODS.xml"):
				MODS_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "MODS", "MODS descriptive metadata", mimetype="text/xml", control_group='M')
				MODS_handle.label = "MODS descriptive metadata"
				file_path = self.Bag.path + "/data/MODS.xml"
				MODS_handle.content = open(file_path)
				MODS_handle.save()

			else:
				# write generic MODS datastream
				MODS_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "MODS", "MODS descriptive metadata", mimetype="text/xml", control_group='M')
				MODS_handle.label = "MODS descriptive metadata"

				raw_MODS = '''
<mods:mods xmlns:mods="http://www.loc.gov/mods/v3" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="3.4" xsi:schemaLocation="http://www.loc.gov/mods/v3 http://www.loc.gov/standards/mods/v3/mods-3-4.xsd">
  <mods:titleInfo>
	<mods:title>%s</mods:title>
  </mods:titleInfo>
  <mods:identifier type="local">%s</mods:identifier>
  <mods:extension>
	<PID>%s</PID>
  </mods:extension>
</mods:mods>
				''' % (self.objMeta['label'], self.objMeta['id'].split(":")[1], self.objMeta['id'])
				print raw_MODS
				MODS_handle.content = raw_MODS
				MODS_handle.save()

			# save and commit object before finishIngest()
			final_save = self.ohandle.save()

			# finish generic ingest
			return self.finishIngest(indexObject=indexObject)


		# exception handling
		except Exception,e:
			print traceback.format_exc()
			print "Volume Ingest Error:",e
			return False


	# function that runs at end of ContentType ingestBag(), running ingest processes generic to ALL objects
	def finishIngest(self, indexObject=True, gen_manifest=False, contentTypeMethods=[]):

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
		os.system('rm %s' % (temp_filename))

		# derive Dublin Core from MODS, update DC datastream
		self.DCfromMODS()

		# Write isWSUDORObject RELS-EXT relationship
		self.ohandle.add_relationship("http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isWSUDORObject","True")

		# the following methods are not needed when objects are "passing through"
		if indexObject:
			# generate OAI identifier
			print self.ohandle.add_relationship("http://www.openarchives.org/OAI/2.0/itemID", "oai:digital.library.wayne.edu:%s" % (self.pid))

			# affiliate with collection set
			try:
				collections = self.previewSolrDict()['rels_isMemberOfCollection']
				for collection in collections:
					print self.ohandle.add_relationship("http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isMemberOfOAISet", collection)
			except:
				print "could not affiliate with collection"

			# Index in Solr (can override from command by setting self.index_on_ingest to False)
			if self.index_on_ingest != False:
				self.indexToSolr()
			else:
				print "Skipping Solr Index"

			# if gen_manifest set, generate IIIF Manifest
			try:
				if gen_manifest == True:
					self.genIIIFManifest(on_demand=True)
			except:
				print "failed on generating IIIF manifest"

			# index object size
			self.update_objSizeDict()

			# run all ContentType specific methods that were passed here
			print "RUNNING ContentType methods..."
			for func in contentTypeMethods:
				func()

		else:
			print "skipping index of object"

		# CLEANUP
		# delete temp_payload, might be dir or symlink
		try:
			print "removing temp_payload directory"
			shutil.rmtree(self.temp_payload)
		except OSError, e:
			# might be symlink
			print "removing temp_payload symlink"
			os.unlink(self.temp_payload)

		# finally, return
		return True


	# def exportBag(self, job_package=False, returnTargetDir=False, preserveRelationships=True):

	# 	'''
	# 	Target Example:
	# 	.
	# 	├── bag-info.txt
	# 	├── bagit.txt
	# 	├── data
	# 	│   ├── datastreams
	# 	│   │   ├── roots.jpg
	# 	│   │   └── trunk.jpg
	# 	│   ├── MODS.xml
	# 	│   └── objMeta.json
	# 	├── manifest-md5.txt
	# 	└── tagmanifest-md5.txt
	# 	'''

	# 	# get PID
	# 	PID = self.pid

	# 	# create temp dir structure
	# 	working_dir = "/tmp/Ouroboros/export_bags"
	# 	# create if doesn't exist
	# 	if not os.path.exists("/tmp/Ouroboros/export_bags"):
	# 		os.mkdir("/tmp/Ouroboros/export_bags")

	# 	temp_dir = working_dir + "/" + str(uuid.uuid4())
	# 	time.sleep(.25)
	# 	os.system("mkdir %s" % (temp_dir))
	# 	time.sleep(.25)
	# 	os.system("mkdir %s/data" % (temp_dir))
	# 	time.sleep(.25)
	# 	os.system("mkdir %s/data/datastreams" % (temp_dir))

	# 	# move bagit files to temp dir, and unpack
	# 	bagit_files = self.ohandle.getDatastreamObject("BAGIT_META").content
	# 	bagitIO = StringIO.StringIO(bagit_files)
	# 	tar_handle = tarfile.open(fileobj=bagitIO)
	# 	tar_handle.extractall(path=temp_dir)

	# 	# export datastreams based on DS ids and objMeta / requires (ds_id,full path filename) tuples to write them
	# 	def writeDS(write_tuple):
	# 		ds_id=write_tuple[0]
	# 		print "WORKING ON",ds_id

	# 		ds_handle = self.ohandle.getDatastreamObject(write_tuple[0])

	# 		# skip if empty (might have been removed / condensed, as case with PDFs)
	# 		if ds_handle.content != None:

	# 			# XML ds model
	# 			if isinstance(ds_handle, eulfedora.models.XmlDatastreamObject) or isinstance(ds_handle, eulfedora.models.RdfDatastreamObject):
	# 				print "FIRING XML WRITER"
	# 				with open(write_tuple[1],'w') as fhand:
	# 					fhand.write(ds_handle.content.serialize())

	# 			# generic ds model (isinstance(ds_handle,eulfedora.models.DatastreamObject))
	# 			'''
	# 			Why is this not writing tiffs?
	# 			'''
	# 			else:
	# 				print "FIRING GENERIC WRITER"
	# 				with open(write_tuple[1],'wb') as fhand:
	# 					for chunk in ds_handle.get_chunked_content():
	# 						fhand.write(chunk)

	# 		else:
	# 			print "Content was NONE for",ds_id,"- skipping..."


	# 	# write original datastreams
	# 	for ds in self.objMeta['datastreams']:
	# 		print "writing %s" % ds
	# 		writeDS((ds['ds_id'],"%s/data/datastreams/%s" % (temp_dir, ds['filename'])))


	# 	# include RELS
	# 	if preserveRelationships == True:
	# 		print "preserving current relationships and writing to RELS-EXT and RELS-INT"
	# 		for rels_ds in ['RELS-EXT','RELS-INT']:
	# 			print "writing %s" % rels_ds
	# 			writeDS((rels_ds,"%s/data/datastreams/%s" % (temp_dir, ds['filename'])))


	# 	# write MODS and objMeta files
	# 	simple = [
	# 		("MODS","%s/data/MODS.xml" % (temp_dir)),
	# 		("OBJMETA","%s/data/objMeta.json" % (temp_dir))
	# 	]
	# 	for ds in simple:
	# 		writeDS(ds)

	# 	# tarball it up
	# 	named_dir = self.pid.replace(":","-")
	# 	os.system("mv %s %s/%s" % (temp_dir, working_dir, named_dir))
	# 	orig_dir = os.getcwd()
	# 	os.chdir(working_dir)
	# 	os.system("tar -cvf %s.tar %s" % (named_dir, named_dir))
	# 	os.system("rm -r %s/%s" % (working_dir, named_dir))

	# 	# move to web accessible location, with username as folder
	# 	if job_package != False:
	# 		username = job_package['username']
	# 	else:
	# 		username = "consoleUser"
	# 	target_dir = "/var/www/wsuls/Ouroboros/export/%s" % (username)
	# 	if os.path.exists(target_dir) == False:
	# 		os.system("mkdir %s" % (target_dir))
	# 	os.system("mv %s.tar %s" % (named_dir,target_dir))

	# 	# jump back to original working dir
	# 	os.chdir(orig_dir)

	# 	if returnTargetDir == True:
	# 		return "%s/%s.tar" % (target_dir,named_dir)
	# 	else:
	# 		return "http://%s/Ouroboros/export/%s/%s.tar" % (localConfig.APP_HOST, username, named_dir)


	# # reingest bag
	# def reingestBag(self, removeExportTar=False, preserveRelationships=True):

	# 	# get PID
	# 	PID = self.pid

	# 	print "Roundrip Ingesting:",PID

	# 	# export bag, returning the file structure location of tar file
	# 	export_tar = self.exportBag(returnTargetDir=True, preserveRelationships=preserveRelationships)
	# 	print "Location of export tar file:",export_tar

	# 	# open bag
	# 	bag_handle = WSUDOR_ContentTypes.WSUDOR_Object(export_tar, object_type='bag')

	# 	# purge self
	# 	if bag_handle != False:
	# 		fedora_handle.purge_object(PID)
	# 	else:
	# 		print "exported object doesn't look good, aborting purge"

	# 	# reingest exported tar file
	# 	bag_handle.ingestBag()

	# 	# delete exported tar
	# 	if removeExportTar == True:
	# 		print "Removing export tar..."
	# 		os.remove(export_tar)

	# 	# return
	# 	return PID,"Reingested."



	# Solr Indexing
	def indexToSolr(self, printOnly=False):

		# derive Dublin Core
		self.DCfromMODS()

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



	# regnerate derivative JP2s
	def regenJP2(self, regenIIIFManifest=False, target_ds=None):
		'''
		Function to recreate derivative JP2s based on JP2DerivativeMaker class in inc/derivatives
		Operates with assumption that datastream ID "FOO_JP2" is derivative as datastream ID "FOO"

		A lot are failing because the TIFFS are compressed, are PNG files.  We need a secondary attempt
		that converts to uncompressed TIFF first.
		'''

		# iterate through datastreams and look for JP2s
		if target_ds is None:
			jp2_ds_list = [ ds for ds in self.ohandle.ds_list if self.ohandle.ds_list[ds].mimeType == "image/jp2" ]
		else:
			jp2_ds_list = [target_ds]

		for i,ds in enumerate(jp2_ds_list):

			print "converting %s, %s / %s" % (ds,str(i),str(len(jp2_ds_list)))

			# init JP2DerivativeMaker
			j = JP2DerivativeMaker(inObj=self)

			# jp2 handle
			jp2_ds_handle = self.ohandle.getDatastreamObject(ds)

			# get original ds_handle
			orig = ds.split("_JP2")[0]
			try:
				orig_ds_handle = self.ohandle.getDatastreamObject(orig)
			except:
				print "could not find original for",orig

			# write temp original and set as inPath
			j.inPath = j.writeTempOrig(orig_ds_handle)

			# gen temp new jp2
			print "making JP2 with",j.inPath,"to",j.outPath
			makeJP2result = j.makeJP2()

			# if fail, try again by uncompressing original temp file
			if makeJP2result == False:
				print "trying again with uncompressed original"
				j.uncompressOriginal()
				makeJP2result = j.makeJP2()

			# last resort, pause, try again
			if makeJP2result == False:
				time.sleep(3)
				makeJP2result = j.makeJP2()

			# write new JP2 datastream
			if makeJP2result:

				with open(j.outPath) as fhand:
					jp2_ds_handle.content = fhand.read()
				print "Result for",ds,jp2_ds_handle.save()

				# cleanup
				os.remove(j.inPath) # input
				j.cleanupTempFiles() # cleanup

				# remove from Loris cache
				self.removeObjFromCache()

			else:
				# cleanup
				# j.cleanupTempFiles()
				raise Exception("Could not regen JP2")


			# if regenIIIFManifest
			if regenIIIFManifest:
				print "regenerating IIIF manifest"
				self.genIIIFManifest()



	def _checkJP2Codestream(self,ds):
		print "Checking integrity of JP2 with jpylyzer..."

		temp_filename = "/tmp/Ouroboros/%s.jp2" % uuid.uuid4()

		ds_handle = self.ohandle.getDatastreamObject(ds)
		with open(temp_filename, 'w') as f:
			for chunk in ds_handle.get_chunked_content():
				f.write(chunk)

		# wrap in try block to make sure we remove the file even if jpylyzer fails
		try:
			# open jpylyzer handle
			jpylyzer_handle = jpylyzer.checkOneFile(temp_filename)
			# check for codestream box
			codestream_check = jpylyzer_handle.find('properties/contiguousCodestreamBox')
			# remove temp file
			os.remove(temp_filename)
			# good JP2
			if type(codestream_check) == etpatch.Element:
				print "codestream found"
				return True
			elif type(codestream_check) == None:
				print "codestream not found"
				return False
			else:
				print "codestream check inconclusive, returning false"
				return False
		except:
			# remove temp file
			os.remove(temp_filename)
			print "codestream check inconclusive, returning false"
			return False



	# from Loris
	def _from_jp2(self,jp2):

		'''
		where 'jp2' is file-like object
		'''

		b = jp2.read(1)
		window =  deque([], 4)
		while ''.join(window) != 'ihdr':
			b = jp2.read(1)
			c = struct.unpack('c', b)[0]
			window.append(c)
		height = int(struct.unpack(">I", jp2.read(4))[0]) # height (pg. 136)
		width = int(struct.unpack(">I", jp2.read(4))[0]) # width
		return (width,height)



	# from Loris
	def _extract_with_pillow(self, fp):
		im = Image.open(fp)
		width,height = im.size
		return (width,height)



	def _imageOrientation(self,dimensions):
		if dimensions[0] > dimensions[1]:
			return "landscape"
		elif dimensions[1] > dimensions[0]:
			return "portrait"
		elif dimensions[0] == dimensions[1]:
			return "square"
		else:
			return False



	def _checkJP2Orientation(self,ds):
		print "Checking aspect ratio of JP2 with Loris"

		# check jp2
		print "checking jp2 dimensions..."
		ds_url = '%s/objects/%s/datastreams/%s/content' % (localConfig.REMOTE_REPOSITORIES['local']['FEDORA_ROOT'], self.pid, ds)
		print ds_url
		uf = urlopen(ds_url)
		jp2_dimensions = self._from_jp2(uf)
		print "JP2 dimensions:", jp2_dimensions, self._imageOrientation(jp2_dimensions)

		# check original
		print "checking original dimensions..."
		ds_url = '%s/objects/%s/datastreams/%s/content' % (localConfig.REMOTE_REPOSITORIES['local']['FEDORA_ROOT'], self.pid, ds.split("_JP2")[0])
		print ds_url
		uf = urlopen(ds_url)
		orig_dimensions = self._extract_with_pillow(uf)
		print "Original dimensions:", orig_dimensions, self._imageOrientation(orig_dimensions)

		if self._imageOrientation(jp2_dimensions) == self._imageOrientation(orig_dimensions):
			print "same orientation"
			return True
		else:
			return False



	# regnerate derivative JP2s
	def checkJP2(self, regenJP2_on_fail=False, tests=['all']):

		'''
		Function to check health and integrity of JP2s for object
		Uses jpylyzer library
		'''

		checks = []

		# iterate through datastreams and look for JP2s
		jp2_ds_list = [ ds for ds in self.ohandle.ds_list if self.ohandle.ds_list[ds].mimeType == "image/jp2" ]

		for i,ds in enumerate(jp2_ds_list):

			print "checking %s, %s / %s" % (ds,i,len(jp2_ds_list))

			# check codesteram present
			if 'all' in tests or 'codestream' in tests:
				checks.append( self._checkJP2Codestream(ds) )

			# check aspect ratio
			if 'all' in tests or 'orientation' in tests:
				checks.append( self._checkJP2Orientation(ds) )

			print "Final checks:", checks

			# if regen on check fail
		if regenJP2_on_fail and False in checks:
			self.regenJP2(regenIIIFManifest=True, target_ds=ds)





	def fixJP2(self):

		'''
		Use checkJP2 to check, fire JP2 if bad
		'''

		print "Checking integrity of JP2 with jpylyzer..."

		if not self.checkJP2():
			self.regenJP2()


	# regnerate derivative JP2s
	def regen_objMeta(self):
		'''
		Function to regen objMeta.  When we decided to let the bag info stored in Fedora not validate,
		opened up the door for editing the objMeta file if things change.

		Add non-derivative datastreams to objMeta, remove objMeta datastreams that no longer exist
		'''

		# get list of current datastreams, sans known derivatives
		new_datastreams = []
		prunable_datastreams = []
		original_datastreams = [ ds['ds_id'] for ds in self.objMeta['datastreams'] ]
		known_derivs = [
			'BAGIT_META',
			'DC',
			'MODS',
			'OBJMETA',
			'POLICY',
			'PREVIEW',
			'RELS-EXT',
			'RELS-INT',
			'THUMBNAIL',
			'HTML_FULL'
		]
		known_suffixes = [
			'_JP2',
			'_PREVIEW',
			'_THUMBNAIL',
			'_ACCESS'
		]

		# look for new datastreams not present in objMeta
		for ds in self.ohandle.ds_list:
			if ds not in known_derivs and len([suffix for suffix in known_suffixes if ds.endswith(suffix)]) == 0 and ds not in original_datastreams:
				new_datastreams.append(ds)
		print "new datastreams:",new_datastreams

		# add new datastream to objMeta
		for ds in new_datastreams:
			ds_handle = self.ohandle.ds_list[ds]
			new_ds = {
				'ds_id':ds,
				'filename':ds,
				'internal_relationships':{},
				'label':ds_handle.label,
				'mimetype':ds_handle.mimeType
			}
			self.objMeta['datastreams'].append(new_ds)

		# look for datastreams in objMeta that should be removed
		for ds in self.objMeta['datastreams']:
			if ds['ds_id'] not in self.ohandle.ds_list:
				prunable_datastreams.append(ds['ds_id'])
		print "prunable datastreams",prunable_datastreams

		# prune datastream from objMeta
		self.objMeta['datastreams'] = [ ds for ds in self.objMeta['datastreams'] if ds['ds_id'] not in prunable_datastreams ]

		# resulting objMeta datastreams
		print "Resulting objMeta datastreams",self.objMeta['datastreams']

		# write current objMeta to fedora datastream
		objMeta_handle = self.ohandle.getDatastreamObject('OBJMETA')
		objMeta_handle.content = json.dumps(self.objMeta)
		objMeta_handle.save()


	# remove object from Loris, Varnish, and other caches
	def removeObjFromCache(self):

		results = {}

		# remove from Loris
		results['loris'] = self._removeObjFromLorisCache()

		# remove from Varnish
		results['varnish'] = self._removeObjFromVarnishCache()

		# return results dictionary
		return results


	# ban image from varnish cache
	def _removeObjFromVarnishCache(self):

		return os.system('varnishadm -S /home/ouroboros/varnish_secret -T localhost:6082 "ban req.url ~ %s"' % self.pid)


	# remove from Loris cache
	def _removeObjFromLorisCache(self):

		removed = []

		for ds in self.ohandle.ds_list:
			if self._removeDatastreamFromLorisCache(ds):
				removed.append(ds)

		print "Cleared from Loris cache:",removed

		return removed



	# remove from Loris cache
	def _removeDatastreamFromLorisCache(self, ds):

		'''
		As we now use Varnish for caching tiles and client<->Loris requests,
		we cannot ascertain as well the file path of the Loris<->Fedora cache.

		Now, requires datastream to purge from cache.
		'''

		print "Removing object from Loris caches..."

		# read config file for Loris
		data = StringIO.StringIO('\n'.join(line.strip() for line in open('/etc/loris2/loris2.conf')))
		config = ConfigParser.ConfigParser()
		config.readfp(data)

		# get cache location(s)
		image_cache = config.get('img.ImageCache','cache_dp').replace("'","")
		if image_cache.endswith('/'):
			image_cache = image_cache[:-1]
		print image_cache

		# craft ident
		ident = "fedora:%s|%s" % (self.pid, ds)

		# clear from fedora resolver cache
		try:
			print "removing instance: %s" % ident
			file_structure = ''
			ident_hash = hashlib.md5(quote_plus(ident)).hexdigest()
			file_structure_list = [ident_hash[0:2]] + [ident_hash[i:i+3] for i in range(2, len(ident_hash), 3)]
			for piece in file_structure_list:
				file_structure = os.path.join(file_structure, piece)
				final_file_structure = "%s/fedora/wayne/%s" % ( image_cache, file_structure )
			print "removing dir: %s" % final_file_structure
			shutil.rmtree(final_file_structure)
			return True
		except:
			print "could not remove from fedora resolver cache"
			return False



	# refresh object
	def objectRefresh(self):

		'''
		Function to update / refresh object properties requisite for front-end.
		Runs multiple object methods under one banner.

		Includes following methods:
		- generate IIIF manifest --> self.genIIIFManifest()
		- update object size in Solr --> self.update_objSizeDict()
		- index in Solr --> self.indexToSolr()
		'''

		try:
			# index in Solr
			self.indexToSolr()

			# generate IIIF manifest
			self.genIIIFManifest()

			# update object size in Solr
			self.update_objSizeDict()

			# remove object from Loris cache
			self.removeObjFromCache()

			return True

		except:
			return False


	# method to send object to remote repository
	def sendObject(self, dest_repo, export_context='migrate', overwrite=False, show_progress=False, refresh_remote=True, omit_checksums=False):

		'''
		dest_repo = string key from localConfig for remote repositories credentials
		'''

		# handle string or eulfedora handle
		print dest_repo,type(dest_repo)
		if type(dest_repo) == str or type(dest_repo) == unicode:
			dest_repo_handle = fedoraHandles.remoteRepo(dest_repo)
		elif type(dest_repo) == eulfedora.server.Repository:
			dest_repo_handle = dest_repo
		else:
			print "destination eulfedora not found, try again"
			return False

		# use syncutil
		print "sending object..."
		result = syncutil.sync_object(
			self.ohandle,
			dest_repo_handle,
			export_context=export_context,
			overwrite=overwrite,
			show_progress=show_progress,
			omit_checksums=omit_checksums)

		# refresh object in remote repo (requires refreshObject() method in remote Ouroboros)
		if type(dest_repo) == str or type(dest_repo) == unicode:
			if refresh_remote:
				print "refreshing remote object in remote repository"
				refresh_remote_url = '%s/tasks/objectRefresh/%s' % (localConfig.REMOTE_REPOSITORIES[dest_repo]['OUROBOROS_BASE_URL'], self.pid)
				print refresh_remote_url
				r = requests.get( refresh_remote_url )
				print r.content
			else:
				print "skipping remote refresh"
		else:
			print "Cannot refresh remote.  It is likely you passed an Eulfedora Repository object.  To refresh remote, please provide string of remote repository that aligns with localConfig"



	# enrich metadata from METS file
	def enrichMODSFromMETS(self, METS_handle, DMDID_prefix="UP00", auto_commit=True):

		'''
		1) read <mods:extension>/<orig_filename>
		2) look for DMDID_prefix + orig_filename
		3) if found, grab MODS from METS
		4) update object MODS
		5) recreate <mods:extension>/<orig_filename> if lost
		'''

		ipytho

		# METS root
		METS_root = METS_handle.getroot()

		# MODS handle
		MODS_handle = self.ohandle.getDatastreamObject('MODS')

		# 1) read <mods:extension>/<orig_filename>
		orig_filename = MODS_handle.content.node.xpath('//mods:extension/orig_filename', namespaces=METS_root.nsmap)
		print orig_filename #DEBUG
		if len(orig_filename) == 1:
			orig_filename = orig_filename[0].text
		elif len(orig_filename) > 1:
			print "multiple orig_filename elements found, aborting"
			return False
		elif len(orig_filename) == 0:
			print "no orig_filename elements found, aborting"
			return False
		else:
			print "could not determine orig_filename"
			return False

		'''
		Need to determine if orig_filename ends with file extension, which we would strip
		or is other.

		Probably safe to assume that file extensions are not *entirely* numbers, which the following
		checks for.
		'''

		# check if orig_filename contains file extension, if so, strip
		full_orig_filename = orig_filename
		parts = orig_filename.split('.')
		try:
			int(parts[-1])
			file_ext_present = False
			print "assuming NOT file extension - keeping orig_filename"
		except:
			file_ext_present = True
			print "assuming file extension present - stripping"
			orig_filename = ".".join(parts[:-1])


		# 2) look for DMDID_prefix + orig_filename
		dmd = METS_root.xpath('//mets:dmdSec[@ID="%s%s"]' % (DMDID_prefix, orig_filename), namespaces=METS_root.nsmap)
		print dmd #DEBUG
		if len(dmd) == 1:
			print "one DMD section found!"
		elif len(dmd) > 1:
			print "multiple DMD sections found, aborting"
			return False
		elif len(dmd) == 0:
			print "no DMD sections found, aborting"
			return False


		# 3) if found, grab MODS from METS
		enriched_MODS = dmd[0].xpath('.//mods:mods',namespaces=METS_root.nsmap)
		print enriched_MODS # DEBUG
		if len(enriched_MODS) == 1:
			print "MODS found"
		elif len(enriched_MODS) > 1:
			print "multiple MODS found, aborting"
			return False
		elif len(enriched_MODS) == 0:
			print "no MODS found, aborting"
			return False


		# 4) update object MODS
		MODS_handle.content = etree.tostring(enriched_MODS[0])
		MODS_handle.save()


		# 5) recreate <mods:extension>/<orig_filename> if lost (taken from MODS export)
		print "ensuring that <orig_filename> endures"

		# reinit MODS and ohandle
		self.ohandle = fedora_handle.get_object(self.pid)
		MODS_handle = self.ohandle.getDatastreamObject('MODS')

		# does <PID> element already exist?
		orig_filename = MODS_handle.content.node.xpath('//mods:extension/orig_filename', namespaces=MODS_handle.content.node.nsmap)

		# if not, continue with checks
		if len(orig_filename) == 0:

			# check for <mods:extension>, if not present add
			extension_check = MODS_handle.content.node.xpath('//mods:extension', namespaces=MODS_handle.content.node.nsmap)

			# if absent, create with <PID> subelement
			if len(extension_check) == 0:
				#serialize and replace
				MODS_content = MODS_handle.content.serialize()
				# drop original full filename back in here
				MODS_content = MODS_content.replace("</mods:mods>","<mods:extension><orig_filename>%s</orig_filename></mods:extension></mods:mods>" % full_orig_filename)

			# <mods:extension> present, but no PID subelement, create
			else:
				orig_filename_elem = etree.SubElement(extension_check[0],"orig_filename")
				orig_filename_elem.text = full_orig_filename
				#serialize
				MODS_content = MODS_handle.content.serialize()

		# overwrite with PID
		else:
			orig_filename_elem = orig_filename[0]
			orig_filename_elem.text = full_orig_filename

			#serialize
			MODS_content = MODS_handle.content.serialize()

		# finall, write content back to MODS
		MODS_handle.content = MODS_content
		MODS_handle.save()



	################################################################
	# Consider moving
	################################################################
	# derive DC from MODS
	def DCfromMODS(self):

		# 1) retrieve MODS
		MODS_handle = self.ohandle.getDatastreamObject('MODS')
		XMLroot = etree.fromstring(MODS_handle.content.serialize())

		# 2) transform downloaded MODS to DC with LOC stylesheet
		print "XSLT Transforming: %s" % (self.pid)
		# Saxon transformation
		XSLhand = open('inc/xsl/MODS_to_DC.xsl','r')
		xslt_tree = etree.parse(XSLhand)
		transform = etree.XSLT(xslt_tree)
		DC = transform(XMLroot)

		# 2.5) scrub duplicate, identical elements from DC
		DC = utilities.delDuplicateElements(DC)

		# 3) save to DC datastream
		DS_handle = self.ohandle.getDatastreamObject("DC")
		DS_handle.content = str(DC)
		derive_results = DS_handle.save()
		print "DCfromMODS result:",derive_results
		return derive_results
