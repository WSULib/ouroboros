#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import mimetypes
import json
import uuid
# import Image
from PIL import Image
import time
import traceback
import sys
import ast

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
from WSUDOR_API.functions.packagedFunctions import singleObjectPackage

# import manifest factory instance
from inc.manifest_factory import iiif_manifest_factory_instance

# derivatives
from inc.derivatives import JP2DerivativeMaker

import localConfig


class WSUDOR_Image(WSUDOR_ContentTypes.WSUDOR_GenObject):

	# static values for class
	label = "Image"

	description = "The Image Content Type contains original / master images, with derivatives for online viewing."

	Fedora_ContentType = "CM:Image"

	def __init__(self,object_type=False,content_type=False,payload=False,orig_payload=False):
		
		# run __init__ from parent class
		WSUDOR_ContentTypes.WSUDOR_GenObject.__init__(self,object_type, content_type, payload, orig_payload)
		
		# Add WSUDOR_Image struct_requirements to WSUDOR_Object instance struct_requirements
		self.struct_requirements['WSUDOR_Image'] = {
			"datastreams":[
				{
					"id":"*_JP2",
					"purpose":"Fullsized, tiled JP2 version of the original image",
					"mimetype":"image/jp2"
				},
				{
					"id":"*_ACCESS",
					"purpose":"Fullsized JPEG of original",
					"mimetype":"image/jpeg"
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


		# finally, return verdict
		return results_dict


	# ingest image type
	def ingestBag(self, indexObject=True):

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
			# objMeta_handle.content = json.dumps(self.objMeta)
			file_path = self.Bag.path + "/data/objMeta.json"
			objMeta_handle.content = open(file_path)
			objMeta_handle.save()

			# -------------------------------------- RELS-EXT ---------------------------------------#

			# write explicit RELS-EXT relationships			
			for relationship in self.objMeta['object_relationships']:
				print "Writing relationship:",str(relationship['predicate']),str(relationship['object'])
				self.ohandle.add_relationship(str(relationship['predicate']),str(relationship['object']))
			
			# writes derived RELS-EXT			
			# isRepresentedBy
			self.ohandle.add_relationship("http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isRepresentedBy",self.objMeta['isRepresentedBy'])
			
			# hasContentModel
			content_type_string = str("info:fedora/CM:"+self.objMeta['content_type'].split("_")[1])
			print "Writing ContentType relationship:","info:fedora/fedora-system:def/relations-external#hasContentModel",content_type_string
			self.ohandle.add_relationship("info:fedora/fedora-system:def/relations-external#hasContentModel",content_type_string)

			# -------------------------------------- RELS-EXT ---------------------------------------#

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
	<mods:title>{label}</mods:title>
  </mods:titleInfo>
  <mods:identifier type="local">{identifier}</mods:identifier>
  <mods:extension>
	<PID>{PID}</PID>
  </mods:extension>
</mods:mods>
				'''.format(label=self.objMeta['label'], identifier=self.objMeta['id'].split(":")[1], PID=self.objMeta['id'])
				print raw_MODS
				MODS_handle.content = raw_MODS		
				MODS_handle.save()

			# create derivatives and write datastreams
			for ds in self.objMeta['datastreams']:

				if "skip_processing" not in ds:		
					print "Processing derivative"		
					file_path = self.Bag.path + "/data/datastreams/" + ds['filename']
					print "Looking for:",file_path

					# original
					orig_handle = eulfedora.models.FileDatastreamObject(self.ohandle, ds['ds_id'], ds['label'], mimetype=ds['mimetype'], control_group='M')
					orig_handle.label = ds['label']
					orig_handle.content = open(file_path)
					orig_handle.save()

					# make access
					temp_filename = "/tmp/Ouroboros/"+str(uuid.uuid4())+".jpg"
					im = Image.open(file_path)
					
					# run through filter
					im = imMode(im)

					im.save(temp_filename,'JPEG')
					preview_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "{ds_id}_ACCESS".format(ds_id=ds['ds_id']), "{label}_ACCESS".format(label=ds['label']), mimetype="image/jpeg", control_group='M')
					preview_handle.label = "{label}_ACCESS".format(label=ds['label'])
					preview_handle.content = open(temp_filename)
					preview_handle.save()
					os.system('rm {temp_filename}'.format(temp_filename=temp_filename))
					
					# make thumb			
					temp_filename = "/tmp/Ouroboros/"+str(uuid.uuid4())+".jpg"
					im = Image.open(file_path)
					width, height = im.size
					max_width = 200	
					max_height = 200

					# run through filter
					im = imMode(im)

					im.thumbnail((max_width, max_height), Image.ANTIALIAS)
					im.save(temp_filename,'JPEG')
					thumb_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "{ds_id}_THUMBNAIL".format(ds_id=ds['ds_id']), "{label}_THUMBNAIL".format(label=ds['label']), mimetype="image/jpeg", control_group='M')
					thumb_handle.label = "{label}_THUMBNAIL".format(label=ds['label'])
					thumb_handle.content = open(temp_filename)
					thumb_handle.save()
					os.system('rm {temp_filename}'.format(temp_filename=temp_filename))

					# make preview
					temp_filename = "/tmp/Ouroboros/"+str(uuid.uuid4())+".jpg"
					im = Image.open(file_path)
					width, height = im.size
					max_width = 1280	
					max_height = 960
					
					# run through filter
					im = imMode(im)

					im.thumbnail((max_width, max_height), Image.ANTIALIAS)
					im.save(temp_filename,'JPEG')
					preview_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "{ds_id}_PREVIEW".format(ds_id=ds['ds_id']), "{label}_PREVIEW".format(label=ds['label']), mimetype="image/jpeg", control_group='M')
					preview_handle.label = "{label}_PREVIEW".format(label=ds['label'])
					preview_handle.content = open(temp_filename)
					preview_handle.save()
					os.system('rm {temp_filename}'.format(temp_filename=temp_filename))

					# make JP2 with derivative class	
					jp2_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "{ds_id}_JP2".format(ds_id=ds['ds_id']), "{label}_JP2".format(label=ds['label']), mimetype="image/jp2", control_group='M')
					jp2_handle.label = "{label}_JP2".format(label=ds['label'])	
					j = JP2DerivativeMaker(inObj=self)
					j.inPath = file_path 
					print "making JP2 with",j.inPath,"to",j.outPath
					makeJP2result = j.makeJP2()

					# if fail, try again by uncompressing original temp file
					if makeJP2result == False:
						print "trying again with uncompressed original"
						j.uncompressOriginal()
						makeJP2result = j.makeJP2()

					# if that fails, attempt to make tiff from original
					if makeJP2result == False:
						print "attempting to create tiff form origianl file format"
						j.createTiffFromOriginal()
						if os.path.exists(j.inPath+".tif"):
							print "rewriting inPath file"
							# change input path for new .tif extension
							j.inPath = j.inPath+".tif"
						makeJP2result = j.makeJP2()

					# last resort, pause, try again
					if makeJP2result == False:
						time.sleep(3)
						makeJP2result = j.makeJP2()

					# write new JP2 datastream
					if makeJP2result:
						with open(j.outPath) as fhand:
							jp2_handle.content = fhand.read()
						print "Result for",ds,jp2_handle.save()
						# cleanup
						j.cleanupTempFiles()					

					else:
						# cleanup
						j.cleanupTempFiles()
						raise Exception("Could not regen JP2")

					# -------------------------------------- RELS-INT ---------------------------------------#

					# add to RELS-INT
					fedora_handle.api.addRelationship(self.ohandle,'info:fedora/{pid}/{ds_id}'.format(pid=self.ohandle.pid,ds_id=ds['ds_id']),'info:fedora/fedora-system:def/relations-internal#isPartOf','info:fedora/{pid}'.format(pid=self.ohandle.pid))
					fedora_handle.api.addRelationship(self.ohandle,'info:fedora/{pid}/{ds_id}_THUMBNAIL'.format(pid=self.ohandle.pid,ds_id=ds['ds_id']),'info:fedora/fedora-system:def/relations-internal#isThumbnailOf','info:fedora/{pid}/{ds_id}'.format(pid=self.ohandle.pid,ds_id=ds['ds_id']))
					fedora_handle.api.addRelationship(self.ohandle,'info:fedora/{pid}/{ds_id}_JP2'.format(pid=self.ohandle.pid,ds_id=ds['ds_id']),'info:fedora/fedora-system:def/relations-internal#isJP2Of','info:fedora/{pid}/{ds_id}'.format(pid=self.ohandle.pid,ds_id=ds['ds_id']))
					fedora_handle.api.addRelationship(self.ohandle,'info:fedora/{pid}/{ds_id}_PREVIEW'.format(pid=self.ohandle.pid,ds_id=ds['ds_id']),'info:fedora/fedora-system:def/relations-internal#isPreviewOf','info:fedora/{pid}/{ds_id}'.format(pid=self.ohandle.pid,ds_id=ds['ds_id']))
					fedora_handle.api.addRelationship(self.ohandle,'info:fedora/{pid}/{ds_id}_ACCESS'.format(pid=self.ohandle.pid,ds_id=ds['ds_id']),'info:fedora/fedora-system:def/relations-internal#isAccessOf','info:fedora/{pid}/{ds_id}'.format(pid=self.ohandle.pid,ds_id=ds['ds_id']))

					# if order present, get order and write relationship. 
					if 'order' in ds:
						fedora_handle.api.addRelationship(self.ohandle,'info:fedora/{pid}/{ds_id}'.format(pid=self.ohandle.pid,ds_id=ds['ds_id']),'info:fedora/fedora-system:def/relations-internal#isOrder', ds['order'], isLiteral=True)

					# -------------------------------------- RELS-INT ---------------------------------------#

				
				# else, skip processing and write straight 1:1 datastream
				else:
					print "Skipping derivative processing"
					file_path = self.Bag.path + "/data/datastreams/" + ds['filename']
					print "Looking for:",file_path

					# original
					generic_handle = eulfedora.models.FileDatastreamObject(self.ohandle, ds['ds_id'], ds['label'], mimetype=ds['mimetype'], control_group='M')
					generic_handle.label = ds['label']
					generic_handle.content = open(file_path)
					generic_handle.save()



			# write generic thumbnail and preview
			'''
			NOTE: This will fail if you skip processing of the isRepresentedBy for any reason, as there will be no _THUMBNAIL
			'''
			for gen_type in ['THUMBNAIL','PREVIEW']:
				rep_handle = eulfedora.models.DatastreamObject(self.ohandle,gen_type, gen_type, mimetype="image/jpeg", control_group="M")
				rep_handle.ds_location = "http://{APP_HOST}/fedora/objects/{pid}/datastreams/{ds_id}_{gen_type}/content".format(pid=self.ohandle.pid,ds_id=self.objMeta['isRepresentedBy'],gen_type=gen_type,APP_HOST=localConfig.APP_HOST)
				rep_handle.label = gen_type
				rep_handle.save()


			# save and commit object before finishIngest()
			final_save = self.ohandle.save()

			# finish generic ingest
			# may pass methods here that will run in finishIngest() 
			return self.finishIngest(gen_manifest=True, indexObject=indexObject, contentTypeMethods=[])


		# exception handling
		except Exception,e:
			print traceback.format_exc()
			print "Image Ingest Error:",e
			return False



	# ingest image type
	def genIIIFManifest(self, on_demand=False):

		# run singleObjectPackage
		'''
		A bit of a hack here: creating getParams{} with pid as list[] as expected by singleObjectPackage(),
		simulates normal WSUDOR_API use of singleObjectPackage()
		'''
		getParams = {}
		getParams['PID'] = [self.pid]

		# run singleObjectPackage() from API
		if on_demand == True:
			getParams['on_demand'] = True
			single_json = json.loads(singleObjectPackage(getParams))
		else:
			single_json = json.loads(singleObjectPackage(getParams))
			
			
		# create root mani obj
		try:
			manifest = iiif_manifest_factory_instance.manifest( label=single_json['objectSolrDoc']['mods_title_ms'][0] )
		except:
			manifest = iiif_manifest_factory_instance.manifest( label="Unknown Title" )
		manifest.viewingDirection = "left-to-right"

		# build metadata
		'''
		Order of preferred fields is the order they will show on the viewer
		NOTE: solr items are stored here as strings so they won't evaluate
		'''
		preferred_fields = [
			("Title", "single_json['objectSolrDoc']['mods_title_ms'][0]"),
			("Description", "single_json['objectSolrDoc']['mods_abstract_ms'][0]"),
			("Year", "single_json['objectSolrDoc']['mods_key_date_year'][0]"),
			("Item URL", "\"<a href='{url}'>{url}</a>\".format(url=single_json['objectSolrDoc']['mods_location_url_ms'][0])"),
			("Original", "single_json['objectSolrDoc']['mods_otherFormat_note_ms'][0]")
		]
		for field_set in preferred_fields:
			try:
				manifest.set_metadata({ field_set[0]:eval(field_set[1]) })
			except:
				print "Could Not Set Metadata Field, Skipping",field_set[0]
	
		# start anonymous sequence
		seq = manifest.sequence(label="default sequence")

		# iterate through component parts
		for image in single_json['parts_imageDict']['sorted']:			
			
			# generate obj|ds identifier as defined in loris TemplateHTTP extension
			fedora_http_ident = "fedora:%s|%s" % (self.pid,image['jp2'])
			# fedora_http_ident = "%s|%s" % (self.pid,image['jp2']) #loris_dev

			# Create a canvas with uri slug of page-1, and label of Page 1
			cvs = seq.canvas(ident=fedora_http_ident, label=image['ds_id'])

			# Create an annotation on the Canvas
			anno = cvs.annotation()

			# Add Image: http://www.example.org/path/to/image/api/p1/full/full/0/native.jpg
			img = anno.image(fedora_http_ident, iiif=True)

			# OR if you have an IIIF service:
			img.set_hw_from_iiif()

			cvs.height = img.height
			cvs.width = img.width


		# insert into Redis and return JSON string
		print "Inserting manifest for",self.pid,"into Redis..."
		redisHandles.r_iiif.set(self.pid,manifest.toString())
		return manifest.toString()	


# helpers
def imMode(im):
	# check for 16-bit tiffs
	print "Image mode:",im.mode				
	if im.mode in ['I;16','I;16B']:
		print "I;16 tiff detected, converting..."
		im.mode = 'I'
		im = im.point(lambda i:i*(1./256)).convert('L')
	# else if not RGB, convert
	elif im.mode != "RGB" :
		print "Converting to RGB"
		im = im.convert("RGB")

	return im























