#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import mimetypes
import json
import uuid
from PIL import Image, ImageDraw, ImageFont
import time
import traceback
import sys
import re
from bs4 import BeautifulSoup
import requests
import rdflib
from collections import defaultdict, OrderedDict

# eulfedora
import eulfedora

# WSUDOR
import WSUDOR_ContentTypes
from WSUDOR_ContentTypes import logging
logging = logging.getChild("WSUDOR_Object")
from WSUDOR_Manager.solrHandles import solr_handle, solr_bookreader_handle
from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager import redisHandles, helpers, utilities
from inc.derivatives import Derivative
from inc.derivatives.image import ImageDerivative

# localconfig
import localConfig


class WSUDOR_WSUebook_Page(WSUDOR_ContentTypes.WSUDOR_GenObject):

	# static values for class
	label = "WSUebook Page"
	description = "Page Model for the WSUebook"
	Fedora_ContentType = "CM:WSUebookPage"

	def __init__(self, object_type=False, content_type=False, payload=False, orig_payload=False):

		# run __init__ from parent class
		WSUDOR_ContentTypes.WSUDOR_GenObject.__init__(self,object_type, content_type, payload, orig_payload)

		# holder for book_obj
		self.book_obj = False

		# empty destinations for concatenated content
		self.html_concat = ''

		# if missing page, save dimensions
		self.faux_width = False
		self.faux_height = False

		# content-type methods run and returned to API
		self.public_api_additions = []


	# page order
	@helpers.LazyProperty
	def order(self):

		# get ordered, constituent objs
		sparql_response = fedora_handle.risearch.sparql_query('select $pageOrder WHERE {{ <info:fedora/%s> <http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/pageOrder> $pageOrder . }}' % (self.pid))
		return int(sparql_response.next()['pageOrder'])


	# ingest
	def ingestBag(self, indexObject=True):

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

		# write explicit RELS-EXT relationships
		for relationship in self.objMeta['object_relationships']:
			logging.debug("Writing relationship: %s %s" % (str(relationship['predicate']),str(relationship['object'])))
			self.ohandle.add_relationship(str(relationship['predicate']),str(relationship['object']))

		# writes derived RELS-EXT
		self.ohandle.add_relationship("http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isRepresentedBy", self.objMeta['isRepresentedBy'])

		# hasContentModel
		content_type_string = "info:fedora/CM:WSUebook_Page"
		logging.debug("Writing ContentType relationship: info:fedora/fedora-system:def/relations-external#hasContentModel %s" % content_type_string)
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
			logging.debug("%s" % raw_MODS)
			MODS_handle.content = raw_MODS
			MODS_handle.save()

		# for each file type in pages dict, pass page obj and process
		for ds in self.objMeta['datastreams']:

			if ds['ds_id'] == 'IMAGE':
				logging.debug("processing image...")
				self.processImage(ds)
			if ds['ds_id'] == 'HTML':
				logging.debug("processing HTML...")
				self.processHTML(ds)
			if ds['ds_id'] == 'ALTOXML':
				logging.debug("processing ALTO...")
				self.processALTOXML(ds)
			if ds['ds_id'] == 'PDF':
				logging.debug("processing PDF...")
				self.processPDF(ds)

		# save and commit object before finishIngest()
		final_save = self.ohandle.save()

		# finish generic ingest
		# may pass methods here that will run in finishIngest()
		return self.finishIngest(gen_manifest=False, indexObject=False, contentTypeMethods=[])


	
	def ingest(self, book_obj, page_num):

		'''
		overrides .ingest() method from WSUDOR_Object
		'''

		# set book_obj to self
		self.book_obj = book_obj

		# using parent book, get datastreams from objMeta
		page_dict = self.book_obj.normalized_pages_from_objMeta[page_num]

		# new pid
		npid = "wayne:%s_Page_%s" % (self.book_obj.pid.split(":")[1], page_num)
		logging.debug("Page pid: %s" % npid)
		self.pid = npid

		# set status as hold
		self.add_to_indexer_queue(action='hold')

		# creating new self	
		self.ohandle = fedora_handle.get_object(npid)
		if self.ohandle.exists:
			fedora_handle.purge_object(self.ohandle)
		self.ohandle = fedora_handle.get_object(npid, create=True)
		self.ohandle.save()

		# label
		self.ohandle.label = "%s - Page %s" % (self.book_obj.ohandle.label, page_num)

		# write POLICY datastream
		# NOTE: 'E' management type required, not 'R'
		logging.debug("Using policy: %s" % self.book_obj.objMeta['policy'])
		policy_suffix = self.book_obj.objMeta['policy'].split("info:fedora/")[1]
		policy_handle = eulfedora.models.DatastreamObject(self.ohandle, "POLICY", "POLICY", mimetype="text/xml", control_group="E")
		policy_handle.ds_location = "http://localhost/fedora/objects/%s/datastreams/POLICY_XML/content" % (policy_suffix)
		policy_handle.label = "POLICY"
		policy_handle.save()

		# for each file type in pages dict, pass page obj and process
		for ds in page_dict:

			if ds['ds_id'].startswith('IMAGE'):
				logging.debug("processing image...")
				self.processImage(ds)

			if ds['ds_id'].startswith('HTML'):
				logging.debug("processing HTML...")
				self.processHTML(ds)

			if ds['ds_id'].startswith('ALTOXML'):
				logging.debug("processing ALTO...")
				self.processALTOXML(ds)

		# write RDF relationships
		self.ohandle.add_relationship("info:fedora/fedora-system:def/relations-external#hasContentModel", "info:fedora/CM:WSUebook_Page")
		self.ohandle.add_relationship("http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/preferredContentModel", "info:fedora/CM:WSUebook_Page")
		self.ohandle.add_relationship("info:fedora/fedora-system:def/relations-external#isConstituentOf", "info:fedora/%s" % self.book_obj.ohandle.pid)
		self.ohandle.add_relationship("http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/pageOrder", page_num)

		# save page object
		self.ohandle.save()

		# set status as hold
		self.alter_in_indexer_queue('forget')

		# return
		return True


	def ingestMissingPage(self, book_obj, page_num, from_bag=True):

		# set book_obj to self
		self.book_obj = book_obj

		# new pid
		npid = "wayne:%s_Page_%s" % (self.book_obj.pid.split(":")[1], page_num)

		# creating new self	
		self.ohandle = fedora_handle.get_object(npid)
		if self.ohandle.exists:
			fedora_handle.purge_object(self.ohandle)
		self.ohandle = fedora_handle.get_object(npid, create=True)
		self.ohandle.save()

		# label
		self.ohandle.label = "%s - Page %s" % (self.book_obj.ohandle.label, page_num)

		# write POLICY datastream
		# NOTE: 'E' management type required, not 'R'
		logging.debug("Using policy: %s" % self.book_obj.objMeta['policy'])
		policy_suffix = self.book_obj.objMeta['policy'].split("info:fedora/")[1]
		policy_handle = eulfedora.models.DatastreamObject(self.ohandle, "POLICY", "POLICY", mimetype="text/xml", control_group="E")
		policy_handle.ds_location = "http://localhost/fedora/objects/%s/datastreams/POLICY_XML/content" % (policy_suffix)
		policy_handle.label = "POLICY"
		policy_handle.save()				

		logging.debug("Processing HTML placeholder")
		generic_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "HTML", "HTML", mimetype="text/html", control_group='M')
		generic_handle.label = "HTML"
		generic_handle.content = "<p>[Page %s Intentionally Left Blank]</p>" % (page_num)
		generic_handle.save()

		logging.debug("Processing IMAGE placeholder")
		# passes 'from_bag' param		
		self.processImage(None, exists=False, page_num=page_num, from_bag=from_bag)

		# write RDF relationships
		self.ohandle.add_relationship("info:fedora/fedora-system:def/relations-external#hasContentModel", "info:fedora/CM:WSUebook_Page")
		self.ohandle.add_relationship("info:fedora/fedora-system:def/relations-external#isConstituentOf", "info:fedora/%s" % self.book_obj.ohandle.pid)
		self.ohandle.add_relationship("http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/pageOrder", page_num)
		self.ohandle.add_relationship("http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/pageExists", False)

		# create IMAGE, HTML, ALTOXML for missing page
		logging.debug("Processing ALTOXML placeholder")
		generic_handle = eulfedora.models.FileDatastreamObject(self.ohandle, 'ALTOXML', 'ALTOXML', mimetype="text/xml", control_group='M')
		generic_handle.label = 'ALTOXML'
		generic_handle.content = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><alto xmlns="http://www.loc.gov/standards/alto/ns-v2#" xmlns:xlink="http://www.w3.org/1999/xlink"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:schemaLocation="http://www.loc.gov/standards/alto/ns-v2# http://www.loc.gov/standards/alto/alto-v2.0.xsd">    <Description>        <MeasurementUnit>pixel</MeasurementUnit>        <OCRProcessing ID="IdOcr">            <ocrProcessingStep>                <processingSoftware>                    <softwareCreator>ABBYY</softwareCreator>                    <softwareName>ABBYY Recognition Server</softwareName>                    <softwareVersion>4.0</softwareVersion>                </processingSoftware>            </ocrProcessingStep>        </OCRProcessing>    </Description>    <Styles>        <ParagraphStyle ID="StyleId-FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF-" ALIGN="Left" LEFT="0"            RIGHT="0" FIRSTLINE="0"/>    </Styles>    <Layout>        <Page ID="Page1" PHYSICAL_IMG_NR="1">            <PrintSpace HEIGHT="%s" WIDTH="%s" VPOS="0" HPOS="0"/>        </Page>    </Layout></alto>' % (self.faux_width, self.faux_height)
		generic_handle.save()

		# save page object
		return self.ohandle.save()



	def processImage(self, ds, exists=True, page_num=None, from_bag=True):

		if exists:
			logging.debug("Processing derivative")
			file_path = self.Bag.path + "/data/datastreams/" + ds['filename']
			logging.debug("Looking for: %s" % file_path)

		if not exists:

			if from_bag:
				# read first page in book for general size
				first_page_dict = self.book_obj.pages_from_objMeta[self.book_obj.pages_from_objMeta.keys()[0]]
				for ds in first_page_dict:
					if ds['ds_id'].startswith('IMAGE'):
						file_path = self.book_obj.Bag.path + "/data/datastreams/" + ds['filename']
						logging.debug("looking for dimensions from this file: %s" % file_path)
						with Image.open(file_path) as im:
							width, height = im.size
							self.faux_width, self.faux_height = im.size # save for use in ALTOXML
							logging.debug("dimensions: %s %s" (width,height))

			# get dimensions from iiif_manifest
			if not from_bag:
				im = json.loads(self.book_obj.iiif_manifest)
				page_info = im['sequences'][0]['canvases'][0]
				width, height = (page_info['width'],page_info['height'])
				self.faux_width, self.faux_height = (page_info['width'],page_info['height']) # save for use in ALTOXML
				logging.debug("dimensions: %s %s" (width,height))

			# write temp file
			missing_page_output_handle = Derivative.create_temp_file(suffix='.tif')
			file_path = missing_page_output_handle.name
			
			# init blank canvas
			W, H = (width, height)			
			im = Image.new("RGBA",(W,H),"white")
			draw = ImageDraw.Draw(im)

			# write text 
			txt = "[ Cover Intentionally Left Blank ]"
			fontsize = 1  # starting font size
			# portion of image width you want text width to be
			img_fraction = 0.50
			font = ImageFont.truetype("WSUDOR_ContentTypes/assets/Roboto-Regular.ttf", fontsize)
			while font.getsize(txt)[0] < img_fraction*im.size[0]:
				# iterate until the text size is just larger than the criteria
				fontsize += 1
				font = ImageFont.truetype("WSUDOR_ContentTypes/assets/Roboto-Regular.ttf", fontsize)

			# optionally de-increment to be sure it is less than criteria
			fontsize -= 1
			font = ImageFont.truetype("WSUDOR_ContentTypes/assets/Roboto-Regular.ttf", fontsize)
			logging.debug('final font size %s' % fontsize)

			w, h = font.getsize(txt)
			draw.text(((W-w)/2,(H-h)/2), txt, font=font, fill="black")
			im.save(file_path, "TIFF")
			logging.debug("written to %s" % file_path)

		# original
		orig_handle = eulfedora.models.FileDatastreamObject(self.ohandle, 'IMAGE', 'IMAGE', mimetype='image/tiff', control_group='M')
		orig_handle.label = "IMAGE"
		orig_handle.content = open(file_path)
		orig_handle.save()

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
		thumb_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "THUMBNAIL", "THUMBNAIL", mimetype="image/jpeg", control_group='M')
		thumb_handle.label = "THUMBNAIL"
		thumb_handle.content = open(temp_filename)
		thumb_handle.save()
		os.system('rm %s' % (temp_filename))

		# make JP2 with derivative module
		jp2_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "JP2", "JP2", mimetype="image/jp2", control_group='M')
		jp2_handle.label = "JP2"
		jp2 = ImageDerivative(file_path)
		jp2_result = jp2.makeJP2()
		if jp2_result:
			with open(jp2.output_handle.name) as fhand:
				jp2_handle.content = fhand.read()
			logging.debug("Result for %s, %s" % (ds,jp2_handle.save()))
			jp2.output_handle.unlink(jp2.output_handle.name)
		else:
			raise Exception("Could not create JP2")

		# cleanup
		if not exists:
			missing_page_output_handle.unlink(missing_page_output_handle.name)

		

	def processHTML(self, ds):

		logging.debug("Processing HTML")
		file_path = self.Bag.path + "/data/datastreams/" + ds['filename']
		logging.debug("Looking for: %s" % file_path)
		generic_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "HTML", "HTML", mimetype=ds['mimetype'], control_group='M')
		generic_handle.label = "HTML"
		generic_handle.content = open(file_path)
		generic_handle.save()


	def processALTOXML(self, ds):
		logging.debug("Processing ALTO XML")
		file_path = self.Bag.path + "/data/datastreams/" + ds['filename']
		logging.debug("Looking for: %s" % file_path)
		generic_handle = eulfedora.models.FileDatastreamObject(self.ohandle, 'ALTOXML', 'ALTOXML', mimetype=ds['mimetype'], control_group='M')
		generic_handle.label = 'ALTOXML'
		generic_handle.content = open(file_path)
		generic_handle.save()


	def processPDF(self, ds):
		logging.debug("Processing PDF")
		file_path = self.Bag.path + "/data/datastreams/" + ds['filename']
		logging.debug("Looking for: %s" % file_path)
		generic_handle = eulfedora.models.FileDatastreamObject(self.ohandle, 'PDF', 'PDF', mimetype=ds['mimetype'], control_group='M')
		generic_handle.label = 'PDF'
		generic_handle.content = open(file_path)
		generic_handle.save()
		

	def sendAbbyyFiles(self):
		'''
		1) Send image to /tmp/abbyy/incoming/[PID]/IMAGE_[PAGE_NUM].[MIMETYPE]
		2) Wait for return?
		'''

		logging.debug("sending image file to abbyy for %s" % self.pid)

		# open image handle
		image_handle = self.ohandle.getDatastreamObject('IMAGE')
		image_filename = '%s/%s%s' % (localConfig.ABBYY_INCOMING, self.pid.replace(":","_"), utilities.mimetypes.guess_extension(image_handle.mimetype))
		logging.debug("%s" % image_filename)

		# write to file
		with open(image_filename, 'w') as fd:
			fd.write(image_handle.content)


	def checkAbbyyFiles(self):

		stime = time.time()

		# open image handle
		image_handle = self.ohandle.getDatastreamObject('IMAGE')

		# generate list of files to watch for (per the "ouroboros" workflow output in abbyy)
		abbyy_output = [			
			self.pid.replace(":","_") + ".htm",
			self.pid.replace(":","_") + ".pdf",
			self.pid.replace(":","_") + ".txt",
			self.pid.replace(":","_") + ".xml",
		]

		# loop through and wait for files
		if set(abbyy_output).issubset(os.listdir(localConfig.ABBYY_OUTPUT)):
			logging.debug("OCR complete for %s" % self.pid)
			return abbyy_output
		else:
			return False


	def updateAbbyyFiles(self, cleanup=True):

		'''update datastreams with abbyy output'''

		logging.debug("updating ABYYY files for %s" % self.pid)

		# prep filenames
		abbyy_output = {			
			'HTML':localConfig.ABBYY_OUTPUT + "/" + self.pid.replace(":","_") + ".htm",
			'PDF':localConfig.ABBYY_OUTPUT + "/" + self.pid.replace(":","_") + ".pdf",
			'TXT':localConfig.ABBYY_OUTPUT + "/" + self.pid.replace(":","_") + ".txt",
			'ALTOXML':localConfig.ABBYY_OUTPUT + "/" + self.pid.replace(":","_") + ".xml",
		}

		# HTML
		with open(abbyy_output['HTML'],'r') as fd:
			if 'HTML' in self.ohandle.ds_list:
				logging.debug("updating HTML")
				ds_handle = self.ohandle.getDatastreamObject('HTML')
				ds_handle.content = fd.read()
				ds_handle.save()
			else:
				logging.debug("creating HTML datastream")
				ds_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "HTML", "HTML", mimetype="text/html", control_group='M')
				ds_handle.label = "HTML"
				ds_handle.content = fd.read()
				ds_handle.save()
		
		# TXT
		logging.debug("skipping txt for now...")
		
		# ALTOXML
		with open(abbyy_output['ALTOXML'],'r') as fd:
			if 'ALTOXML' in self.ohandle.ds_list:
				logging.debug("updating ALTOXML")
				ds_handle = self.ohandle.getDatastreamObject('ALTOXML')
				ds_handle.content = fd.read()
				ds_handle.save()
			else:
				logging.debug("creating ALTOXML datastream")
				ds_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "ALTOXML", "ALTOXML", mimetype="text/xml", control_group='M')
				ds_handle.label = "ALTOXML"
				ds_handle.content = fd.read()
				ds_handle.save()
		
		# PDF
		'''
		Will require updating full-text PDF
		'''
		logging.debug("skipping pdf for now...")


		# cleanup
		if cleanup:
			for k in abbyy_output:
				os.remove(abbyy_output[k])


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
			logging.debug("for WSUebook_Page type, known original as 'IMAGE'")
			orig = 'IMAGE'
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



# helpers
'''
This might be where we can fix the gray TIFFs
'''
def imMode(im):
	# check for 16-bit tiffs
	logging.debug("Image mode: %s" % im.mode)
	if im.mode in ['I;16','I;16B']:
		logging.debug("I;16 tiff detected, converting...")
		im.mode = 'I'
		im = im.point(lambda i:i*(1./256)).convert('L')
	# else if not RGB, convert
	elif im.mode != "RGB" :
		logging.debug("Converting to RGB")
		im = im.convert("RGB")

	return im





		




