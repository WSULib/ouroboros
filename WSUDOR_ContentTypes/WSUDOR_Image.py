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
from WSUDOR_Manager import celery

# eulfedora
import eulfedora

# WSUDOR
import WSUDOR_ContentTypes
from WSUDOR_ContentTypes import logging
logging = logging.getChild("WSUDOR_Object")
from WSUDOR_Manager.solrHandles import solr_handle
from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager.lmdbHandles import lmdb_env
from WSUDOR_Manager import redisHandles, utilities, helpers
from inc.derivatives import Derivative
from inc.derivatives.image import ImageDerivative

import localConfig


class WSUDOR_Image(WSUDOR_ContentTypes.WSUDOR_GenObject):

	# static values for class
	label = "Image"
	description = "The Image Content Type contains original / master images, with derivatives for online viewing."
	Fedora_ContentType = "CM:Image"
	version = 2

	def __init__(self,object_type=False, content_type=False, payload=False, orig_payload=False):
 
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

		# content-type methods run and returned to API
		self.public_api_additions = [self.imageParts]


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
			report_failure(("isRepresentedBy_check","%s is not in %s" % (self.objMeta['isRepresentedBy'], ds_ids)))


		# check that content_type is a valid ContentType
		if self.__class__ not in WSUDOR_ContentTypes.WSUDOR_GenObject.__subclasses__():
			report_failure(("Valid ContentType","WSUDOR_Object instance's ContentType: %s, not found in acceptable ContentTypes: %s " % (self.content_type, WSUDOR_ContentTypes.WSUDOR_GenObject.__subclasses__())))


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
			logging.debug("Using policy: %s" % self.objMeta['policy'])
			policy_suffix = self.objMeta['policy'].split("info:fedora/")[1]
			policy_handle = eulfedora.models.DatastreamObject(self.ohandle,"POLICY", "POLICY", mimetype="text/xml", control_group="E")
			policy_handle.ds_location = "http://localhost/fedora/objects/%s/datastreams/POLICY_XML/content" % (policy_suffix)
			policy_handle.label = "POLICY"
			policy_handle.save()

			# write objMeta as datastream
			objMeta_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "OBJMETA", "Ingest Bag Object Metadata", mimetype="application/json", control_group='M')
			objMeta_handle.label = "Ingest Bag Object Metadata"
			file_path = self.Bag.path + "/data/objMeta.json"
			objMeta_handle.content = open(file_path)
			objMeta_handle.save()

			# -------------------------------------- RELS-EXT ---------------------------------------#

			# write explicit RELS-EXT relationships
			for relationship in self.objMeta['object_relationships']:
				logging.debug("Writing relationship: %s" % (str(relationship['predicate']),str(relationship['object'])))
				self.ohandle.add_relationship(str(relationship['predicate']),str(relationship['object']))

			# writes derived RELS-EXT
			# isRepresentedBy
			self.ohandle.add_relationship("http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isRepresentedBy",self.objMeta['isRepresentedBy'])

			# hasContentModel
			content_type_string = str("info:fedora/CM:"+self.objMeta['content_type'].split("_")[1])
			logging.debug("Writing ContentType relationship: info:fedora/fedora-system:def/relations-external#hasContentModel %s" % content_type_string)
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
	<mods:title>%s</mods:title>
  </mods:titleInfo>
  <mods:identifier type="local">%s</mods:identifier>
  <mods:extension>
	<PID>%s</PID>
  </mods:extension>
</mods:mods>
				''' % (self.objMeta['label'], self.objMeta['id'].split(":")[1], self.objMeta['id'])
				logging.debug("%s" % raw_MODS)
				MODS_handle.content = raw_MODS
				MODS_handle.save()

			# create derivatives and write datastreams
			for ds in self.objMeta['datastreams']:

				if "skip_processing" not in ds:
					logging.debug("Processing derivative")
					file_path = self.Bag.path + "/data/datastreams/" + ds['filename']
					logging.debug("Looking for: %s" % file_path)

					# original
					orig_handle = eulfedora.models.FileDatastreamObject(self.ohandle, ds['ds_id'], ds['label'], mimetype=ds['mimetype'], control_group='M')
					orig_handle.label = ds['label']
					orig_handle.content = open(file_path)
					orig_handle.save()

					# make access
					temp_filename = "/tmp/Ouroboros/"+str(uuid.uuid4())+".jpg"
					im = Image.open(file_path)

					# run through filter
					im = utilities.imMode(im)

					im.save(temp_filename,'JPEG')
					preview_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "%s_ACCESS" % (ds['ds_id']), "%s_ACCESS" % (ds['label']), mimetype="image/jpeg", control_group='M')
					preview_handle.label = "%s_ACCESS" % (ds['label'])
					preview_handle.content = open(temp_filename)
					preview_handle.save()
					os.system('rm %s' % (temp_filename))

					# make thumb
					temp_filename = "/tmp/Ouroboros/"+str(uuid.uuid4())+".jpg"
					im = Image.open(file_path)
					width, height = im.size
					max_width = 200
					max_height = 200

					# run through filter
					im = utilities.imMode(im)

					im.thumbnail((max_width, max_height), Image.ANTIALIAS)
					im.save(temp_filename,'JPEG')
					thumb_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "%s_THUMBNAIL" % (ds['ds_id']), "%s_THUMBNAIL" % (ds['label']), mimetype="image/jpeg", control_group='M')
					thumb_handle.label = "%s_THUMBNAIL" % (ds['label'])
					thumb_handle.content = open(temp_filename)
					thumb_handle.save()
					os.system('rm %s' % (temp_filename))

					# make preview
					temp_filename = "/tmp/Ouroboros/"+str(uuid.uuid4())+".jpg"
					im = Image.open(file_path)
					width, height = im.size
					max_width = 1280
					max_height = 960

					# run through filter
					im = utlities.imMode(im)

					im.thumbnail((max_width, max_height), Image.ANTIALIAS)
					im.save(temp_filename,'JPEG')
					preview_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "%s_PREVIEW" % (ds['ds_id']), "%s_PREVIEW" % (ds['label']), mimetype="image/jpeg", control_group='M')
					preview_handle.label = "%s_label" % (ds['label'])
					preview_handle.content = open(temp_filename)
					preview_handle.save()
					os.system('rm %s' % (temp_filename))

					# make JP2 with derivative module
					jp2_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "%s_JP2" % (ds['ds_id']), "%s_JPS" % (ds['label']), mimetype="image/jp2", control_group='M')
					jp2_handle.label = "%s_JPS" % (ds['label'])
					jp2 = ImageDerivative(file_path)
					jp2_result = jp2.makeJP2()
					if jp2_result:
						with open(jp2.output_handle.name) as fhand:
							jp2_handle.content = fhand.read()
						logging.debug("Result for %s %s" % (ds,jp2_handle.save()))
						jp2.output_handle.unlink(jp2.output_handle.name)
					else:
						raise Exception("Could not create JP2")

					# -------------------------------------- RELS-INT ---------------------------------------#

					# add to RELS-INT
					fedora_handle.api.addRelationship(self.ohandle,'info:fedora/%s/%s' % (self.ohandle.pid, ds['ds_id']),'info:fedora/fedora-system:def/relations-internal#isPartOf','info:fedora/%s' % (self.ohandle.pid))
					fedora_handle.api.addRelationship(self.ohandle,'info:fedora/%s/%s_THUMBNAIL' % (self.ohandle.pid, ds['ds_id']),'info:fedora/fedora-system:def/relations-internal#isThumbnailOf','info:fedora/%s/%s' % (self.ohandle.pid, ds['ds_id']))
					fedora_handle.api.addRelationship(self.ohandle,'info:fedora/%s/%s_JP2' % (self.ohandle.pid, ds['ds_id']),'info:fedora/fedora-system:def/relations-internal#isJP2Of','info:fedora/%s/%s' % (self.ohandle.pid, ds['ds_id']))
					fedora_handle.api.addRelationship(self.ohandle,'info:fedora/%s/%s_PREVIEW' % (self.ohandle.pid, ds['ds_id']),'info:fedora/fedora-system:def/relations-internal#isPreviewOf','info:fedora/%s/%s' % (self.ohandle.pid, ds['ds_id']))
					fedora_handle.api.addRelationship(self.ohandle,'info:fedora/%s/%s_ACCESS' % (self.ohandle.pid, ds['ds_id']),'info:fedora/fedora-system:def/relations-internal#isAccessOf','info:fedora/%s/%s' % (self.ohandle.pid, ds['ds_id']))

					# if order present, get order and write relationship.
					if 'order' in ds:
						fedora_handle.api.addRelationship(self.ohandle,'info:fedora/%s/%s' % (self.ohandle.pid,ds['ds_id']),'info:fedora/fedora-system:def/relations-internal#isOrder', ds['order'], isLiteral=True)

					# -------------------------------------- RELS-INT ---------------------------------------#


				# else, skip processing and write straight 1:1 datastream
				else:
					logging.debug("Skipping derivative processing")
					file_path = self.Bag.path + "/data/datastreams/" + ds['filename']
					logging.debug("Looking for: %s" % file_path)

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
				rep_handle.ds_location = "http://localhost/fedora/objects/%s/datastreams/%s_%s/content" % (self.ohandle.pid, self.objMeta['isRepresentedBy'], gen_type)
				rep_handle.label = gen_type
				rep_handle.save()


			# save and commit object before finishIngest()
			final_save = self.ohandle.save()

			# finish generic ingest
			# may pass methods here that will run in finishIngest()
			return self.finishIngest(gen_manifest=True, indexObject=indexObject, contentTypeMethods=[])


		# exception handling
		except:
			raise Exception(traceback.format_exc())


	# ingest image type
	def genIIIFManifest(self, on_demand=False):

		# get solr_doc
		solr_doc = self.SolrDoc.asDictionary()

		# create root mani obj
		try:
			manifest = self.iiif_factory.manifest( ident="manifest.json", label=solr_doc['mods_title_ms'][0] )
		except:
			manifest = self.iiif_factory.manifest( ident="manifest.json", label="Unknown Title" )
		manifest.viewingDirection = "left-to-right"

		# build metadata
		'''
		Order of preferred fields is the order they will show on the viewer
		NOTE: solr items are stored here as strings so they won't evaluate
		'''
		preferred_fields = [
			("Title", "solr_doc['mods_title_ms'][0]"),
			("Description", "solr_doc['mods_abstract_ms'][0]"),
			("Year", "solr_doc['mods_key_date_year'][0]"),
			("Item URL", "\"<a href='%s'>%s</a>\" % (solr_doc['mods_location_url_ms'][0],solr_doc['mods_location_url_ms'][0])"),
			("Original", "solr_doc['mods_otherFormat_note_ms'][0]")
		]
		for field_set in preferred_fields:
			try:
				manifest.set_metadata({ field_set[0]:eval(field_set[1]) })
			except:
				logging.debug("Could Not Set Metadata Field, Skipping %s" % field_set[0])

		# start anonymous sequence
		seq = manifest.sequence(label="default sequence")

		# iterate through component parts
		for image in self.imageParts()['sorted']:

			# generate obj|ds identifier as defined in loris TemplateHTTP extension
			fedora_http_ident = "fedora:%s|%s" % (self.pid,image['jp2'])

			# Create a canvas with uri slug of page-1, and label of Page 1
			cvs = seq.canvas(ident=image['jp2'], label=image['ds_id'])

			# Create an annotation on the Canvas
			anno = cvs.annotation()

			# Add Image: http://www.example.org/path/to/image/api/p1/full/full/0/native.jpg
			img = anno.image(fedora_http_ident, iiif=True)

			# OR if you have an IIIF service:
			img.set_hw_from_iiif()

			cvs.height = img.height
			cvs.width = img.width

		# save manifest to LMDB database
		logging.debug("Saving manifest for %s in LMDB database" % self.pid)
		with lmdb_env.begin(write=True) as txn:
			txn.put('%s_iiif_manifest' % (self.pid.encode('utf-8')), manifest.toString().encode('utf-8'))
		
		return manifest.toString()


	# create dictionary comprehensive of all associated images
	def imageParts(self):
		
		'''
		Supplanting `main_imageDict_comp` and `parts_imageDict_comp` from API_legacy
		desc: return dictionary with all image components, including pointer to "main" or representative image
		image_part = {
			ds_id: foobar,
			jp2: foobar_JP2,
			order: 2,			
			preview: foobar_PREVIEW,
			thumbnail: foobar_THUMBNAIL
		}
		'''


		parts_imageDict = {}
		parts_imageDict['parts_list'] = []
		for image in self.hasInternalParts:

			parts_imageDict[image] = {
				'ds_id':image,
				'thumbnail' : fedora_handle.risearch.get_subjects("info:fedora/fedora-system:def/relations-internal#isThumbnailOf", "info:fedora/%s/%s" % (self.pid, image)).next().split("/")[-1],
				'preview' : fedora_handle.risearch.get_subjects("info:fedora/fedora-system:def/relations-internal#isPreviewOf", "info:fedora/%s/%s" % (self.pid, image)).next().split("/")[-1],
				'jp2' : fedora_handle.risearch.get_subjects("info:fedora/fedora-system:def/relations-internal#isJP2Of", "info:fedora/%s/%s" % (self.pid, image)).next().split("/")[-1]
			}

			# check for order and assign
			try:
				order = int(fedora_handle.risearch.get_objects("info:fedora/%s/%s" % (self.pid, image), "info:fedora/fedora-system:def/relations-internal#isOrder").next())
			except:
				order = False
			parts_imageDict[image]['order'] = order

			# add to list
			parts_imageDict['parts_list'].append((parts_imageDict[image]['order'], parts_imageDict[image]['ds_id']))
		

		# sort and make iterable list from dictionary
		parts_imageDict['parts_list'].sort(key=lambda tup: tup[0])
		parts_imageList = []
		for each in parts_imageDict['parts_list']:
			parts_imageList.append(parts_imageDict[each[1]])
		
		# reassign		
		del parts_imageDict['parts_list']
		parts_imageDict['sorted'] = parts_imageList

		# return
		return parts_imageDict


	# regnerate derivative JP2s
	def regenJP2(self, regenIIIFManifest=False, target_ds=None, clear_cache=True):
		'''
		Function to recreate derivative JP2s based on JP2DerivativeMaker class in inc/derivatives
		Operates with assumption that datastream ID "FOO_JP2" is derivative as datastream ID "FOO"
		'''

		# iterate through datastreams and look for JP2s
		if target_ds is None:
			jp2_ds_list = [ ds for ds in self.ohandle.ds_list if self.ohandle.ds_list[ds].mimeType == "image/jp2" ]
		else:
			jp2_ds_list = [target_ds]

		for i, ds in enumerate(jp2_ds_list):

			logging.debug("converting %s, %s / %s" % (ds,str(i+1),str(len(jp2_ds_list))))

			# jp2 handle
			jp2_ds_handle = self.ohandle.getDatastreamObject(ds)

			# get original ds_handle
			orig = ds.split("_JP2")[0]
			try:
				orig_ds_handle = self.ohandle.getDatastreamObject(orig)
			except:
				logging.debug("could not find original for %s" % orig)

			# write temp original and set as inPath
			guessed_ext = utilities.mimetypes.guess_extension(orig_ds_handle.mimetype)
			logging.debug("guessed extension for temporary orig handle: %s" % guessed_ext)
			temp_orig_handle = Derivative.write_temp_file(orig_ds_handle, suffix=guessed_ext)

			# # gen temp new jp2            
			jp2 = ImageDerivative(temp_orig_handle.name)
			jp2_result = jp2.makeJP2()

			if jp2_result:
				with open(jp2.output_handle.name) as fhand:
					jp2_ds_handle.content = fhand.read()
				jp2_ds_handle.save()

				# cleanup
				jp2.output_handle.unlink(jp2.output_handle.name)
				temp_orig_handle.unlink(temp_orig_handle.name)
			else:
				# cleanup
				jp2.output_handle.unlink(jp2.output_handle.name)
				temp_orig_handle.unlink(temp_orig_handle.name)
				raise Exception("Could not create JP2")

			# if regenIIIFManifest
			if regenIIIFManifest:
				logging.debug("regenerating IIIF manifest")
				self.genIIIFManifest()

			if clear_cache:
				logging.debug("clearing cache")
				self.removeObjFromCache()

			return True


	# create dictionary comprehensive of all associated images
	def previewImage(self):

		'''
		Return image/loris params for API to render
			- pid, datastream, region, size, rotation, quality, format
		'''

		image_parts = self.imageParts()
		return (self.pid, image_parts['sorted'][0]['preview'], 'full', 'full', 0, 'default', 'jpg')


	# content_type refresh
	def refresh_content_type(self):

		# regen IIIF manifest
		self.genIIIFManifest()
		




