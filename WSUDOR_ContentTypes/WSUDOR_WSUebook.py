#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import mimetypes
import json
import uuid
from PIL import Image
import time
import traceback
import sys
import re

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
from WSUDOR_API.functions.packagedFunctions import singleObjectPackage

# import manifest factory instance
from inc.manifest_factory import iiif_manifest_factory_instance


# helper function for natural sorting
def natural_sort_key(s, _nsre=re.compile('([0-9]+)')):
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split(_nsre, s)] 


class WSUDOR_WSUebook(WSUDOR_ContentTypes.WSUDOR_GenObject):

	# static values for class
	label = "WSUeBook"

	description = "The WSUDOR_WSUebook content type models most print (but some born digital) resources we have created digital components for each page.  This includes a page image, ALTO XML with information about the location of words on the page, a thumbnail, a PDF (with embedded text), and HTML that semi-closely matches the original formatting (suitable for flowing text).  These objects are best viewed with our eTextReader."

	Fedora_ContentType = "CM:WSUebook"

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


		# consider checking for "equality" in page derivative counts
		# from main.py: if (len(page_images) - 1) == len(thumb_images) == len(HTML_docs) == len(altoXML_docs) == len(pdf_docs) == len(jp2_images):

		
		
		# finally, return verdict
		return results_dict


	# ingest 
	def ingestBag(self):

		#----------------- GENERIC INGEST PROCEDURES, CAN BE FOLDED INTO WSUDOR_Object -----------------#
		
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



			#----------------- / WSU_Ebook specific -----------------#

			# create derivatives and write datastreams
			for ds in self.objMeta['datastreams']:


				'''
				for each datastream:
					- parse number from filename (x)

					- determine mimetype
					
					- if image (maybe look at mimetype?):
						- make THUMB_x
						- make ACCESS_x (1700x1700)
					
					- create fullbook PDF and HTML files

					- index book in bookreader core
				'''


			#----------------- GENERIC INGEST PROCEDURES, CAN BE FOLDED INTO WSUDOR_Object -----------------#

			# write generic thumbnail and preview
			for gen_type in ['THUMBNAIL','PREVIEW']:
				rep_handle = eulfedora.models.DatastreamObject(self.ohandle,gen_type, gen_type, mimetype="image/jpeg", control_group="R")
				rep_handle.ds_location = "http://digital.library.wayne.edu/fedora/objects/{pid}/datastreams/{ds_id}_{gen_type}/content".format(pid=self.ohandle.pid,ds_id=self.objMeta['isRepresentedBy'],gen_type=gen_type)
				rep_handle.label = gen_type
				rep_handle.save()

			#----------------- Finish up -----------------#

			# save and commit object before finishIngest()
			final_save = self.ohandle.save()



			# finish generic ingest
			return self.finishIngest()



		# exception handling
		except Exception,e:
			print traceback.format_exc()
			print "Ingest Error:",e
			return False





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



	# ingest 
	def migrate(self):

		'''
		This function will migrate bags from our multiple-object model (old) to a single-object model (new).
		This will require the following work:
			- export multi-object to single directory
				- consider /repository for this amount of data
			- write objMeta.json file for that object (first time)
			- BagIt
			- create ingest method for single-object ebooks
			- ingest!
			- purge old book?
		'''

		return True


	# ingest image type
	def genIIIFManifest(self):

		# run singleObjectPackage
		'''
		A bit of a hack here: creating getParams{} with pid as list[] as expected by singleObjectPackage(),
		simulates normal WSUDOR_API use of singleObjectPackage()
		'''
		getParams = {}
		getParams['PID'] = [self.pid]

		# run singleObjectPackage() from API
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

		# get component parts
		jp2_obj_PID = self.pid.split(":")[1]+":JP2"
		print "Fetching",jp2_obj_PID
		jp2_handle = fedora_handle.get_object(jp2_obj_PID)

		image_list = [ds for ds in jp2_handle.ds_list if ds.startswith('JP2')]
		image_list.sort(key=natural_sort_key)
		print image_list

		# iterate through component parts
		for image in image_list:
			
			print "adding",image

			'''
			Improvement - use custom HTTP resolver with Loris, passing PID and Datastream id
			'''
			# generate obj|ds self.pid as defined in loris TemplateHTTP extension
			fedora_http_ident = "fedora:%s|%s" % (jp2_obj_PID,image)

			# Create a canvas with uri slug of page-1, and label of Page 1
			cvs = seq.canvas(ident=fedora_http_ident, label=image)

			# Create an annotation on the Canvas
			anno = cvs.annotation()

			# Add Image: http://www.example.org/path/to/image/api/p1/full/full/0/native.jpg
			img = anno.image(fedora_http_ident, iiif=True)

			# OR if you have a IIIF service:
			img.set_hw_from_iiif()

			cvs.height = img.height
			cvs.width = img.width


		# insert into Redis and return JSON string
		print "Inserting manifest for",self.pid,"into Redis..."
		redisHandles.r_iiif.set(self.pid,manifest.toString())
		return manifest.toString()


























