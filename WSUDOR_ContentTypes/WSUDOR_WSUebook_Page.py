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

	
	def ingest(self, book_obj, page_num):

		# set book_obj to self
		self.book_obj = book_obj

		# using parent book, get datastreams from objMeta
		page_dict = self.book_obj.pages_from_objMeta[page_num]

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
		print "Using policy:",self.book_obj.objMeta['policy']
		policy_suffix = self.book_obj.objMeta['policy'].split("info:fedora/")[1]
		policy_handle = eulfedora.models.DatastreamObject(self.ohandle, "POLICY", "POLICY", mimetype="text/xml", control_group="E")
		policy_handle.ds_location = "http://localhost/fedora/objects/%s/datastreams/POLICY_XML/content" % (policy_suffix)
		policy_handle.label = "POLICY"
		policy_handle.save()				

		# generic hash of target ids
		target_ids = {
			'IMAGE':'IMAGE_%d' % page_num,
			'HTML':'HTML_%d' % page_num,
			'ALTOXML':'ALTOXML_%d' % page_num
		}

		# for each file type in pages dict, pass page obj and process
		for ds in page_dict:

			if ds['ds_id'].startswith('IMAGE'):
				self.processImage(ds)
			if ds['ds_id'].startswith('HTML'):
				self.processHTML(ds)
			if ds['ds_id'].startswith('ALTOXML'):
				self.processALTOXML(ds)

		# write RDF relationships
		self.ohandle.add_relationship("info:fedora/fedora-system:def/relations-external#hasContentModel", "info:fedora/CM:WSUebook_Page")
		self.ohandle.add_relationship("info:fedora/fedora-system:def/relations-external#isConstituentOf", "info:fedora/%s" % self.book_obj.ohandle.pid)
		self.ohandle.add_relationship("http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/pageOrder", page_num)

		# save page object
		return self.ohandle.save()


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
		print "Using policy:",self.book_obj.objMeta['policy']
		policy_suffix = self.book_obj.objMeta['policy'].split("info:fedora/")[1]
		policy_handle = eulfedora.models.DatastreamObject(self.ohandle, "POLICY", "POLICY", mimetype="text/xml", control_group="E")
		policy_handle.ds_location = "http://localhost/fedora/objects/%s/datastreams/POLICY_XML/content" % (policy_suffix)
		policy_handle.label = "POLICY"
		policy_handle.save()				

		print "Processing HTML placeholder"
		generic_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "HTML", "HTML", mimetype="text/html", control_group='M')
		generic_handle.label = "HTML"
		generic_handle.content = "<p>[Page %s Intentionally Left Blank]</p>" % (page_num)
		generic_handle.save()

		print "Processing IMAGE placeholder"
		# passes 'from_bag' param		
		self.processImage(None, exists=False, page_num=page_num, from_bag=from_bag)

		# write RDF relationships
		self.ohandle.add_relationship("info:fedora/fedora-system:def/relations-external#hasContentModel", "info:fedora/CM:WSUebook_Page")
		self.ohandle.add_relationship("info:fedora/fedora-system:def/relations-external#isConstituentOf", "info:fedora/%s" % self.book_obj.ohandle.pid)
		self.ohandle.add_relationship("http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/pageOrder", page_num)
		self.ohandle.add_relationship("http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/pageExists", False)

		# create IMAGE, HTML, ALTOXML for missing page
		print "Processing ALTOXML placeholder"
		generic_handle = eulfedora.models.FileDatastreamObject(self.ohandle, 'ALTOXML', 'ALTOXML', mimetype="text/xml", control_group='M')
		generic_handle.label = 'ALTOXML'
		generic_handle.content = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><alto xmlns="http://www.loc.gov/standards/alto/ns-v2#" xmlns:xlink="http://www.w3.org/1999/xlink"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:schemaLocation="http://www.loc.gov/standards/alto/ns-v2# http://www.loc.gov/standards/alto/alto-v2.0.xsd">    <Description>        <MeasurementUnit>pixel</MeasurementUnit>        <OCRProcessing ID="IdOcr">            <ocrProcessingStep>                <processingSoftware>                    <softwareCreator>ABBYY</softwareCreator>                    <softwareName>ABBYY Recognition Server</softwareName>                    <softwareVersion>4.0</softwareVersion>                </processingSoftware>            </ocrProcessingStep>        </OCRProcessing>    </Description>    <Styles>        <ParagraphStyle ID="StyleId-FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF-" ALIGN="Left" LEFT="0"            RIGHT="0" FIRSTLINE="0"/>    </Styles>    <Layout>        <Page ID="Page1" PHYSICAL_IMG_NR="1">            <PrintSpace HEIGHT="%s" WIDTH="%s" VPOS="0" HPOS="0"/>        </Page>    </Layout></alto>' % (self.faux_width, self.faux_height)
		generic_handle.save()

		# save page object
		return self.ohandle.save()



	def processImage(self, ds, exists=True, page_num=None, from_bag=True):

		if exists:
			print "Processing derivative"
			file_path = self.book_obj.Bag.path + "/data/datastreams/" + ds['filename']
			print "Looking for:",file_path

		if not exists:

			if from_bag:
				# read first page in book for general size
				first_page_dict = self.book_obj.pages_from_objMeta[self.book_obj.pages_from_objMeta.keys()[0]]
				for ds in first_page_dict:
					if ds['ds_id'].startswith('IMAGE'):
						file_path = self.book_obj.Bag.path + "/data/datastreams/" + ds['filename']
						print "looking for dimensions from this file:",file_path
						with Image.open(file_path) as im:
							width, height = im.size
							self.faux_width, self.faux_height = im.size # save for use in ALTOXML
							print "dimensions:",width,height

			# get dimensions from iiif_manifest
			if not from_bag:
				im = json.loads(self.book_obj.iiif_manifest)
				page_info = im['sequences'][0]['canvases'][0]
				width, height = (page_info['width'],page_info['height'])
				self.faux_width, self.faux_height = (page_info['width'],page_info['height']) # save for use in ALTOXML
				print "dimensions:",width,height

			# write temp file
			missing_page_output_handle = Derivative.create_temp_file(suffix='.tif')
			file_path = missing_page_output_handle.name
			
			# init blank canvas
			W, H = (width, height)			
			im = Image.new("RGBA",(W,H),"white")
			draw = ImageDraw.Draw(im)

			# write text 
			txt = "[Page %s Intentionally Left Blank]" % (page_num)
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
			print 'final font size',fontsize

			w, h = font.getsize(txt)
			draw.text(((W-w)/2,(H-h)/2), txt, font=font, fill="black")
			im.save(file_path, "TIFF")
			print "written to",file_path

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
			print "Result for",ds,jp2_handle.save()
			jp2.output_handle.unlink(jp2.output_handle.name)
		else:
			raise Exception("Could not create JP2")

		# cleanup
		if not exists:
			missing_page_output_handle.unlink(missing_page_output_handle.name)

		

	def processHTML(self, ds):

		print "Processing HTML"
		file_path = self.book_obj.Bag.path + "/data/datastreams/" + ds['filename']
		print "Looking for:",file_path
		generic_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "HTML", "HTML", mimetype=ds['mimetype'], control_group='M')
		generic_handle.label = "HTML"
		generic_handle.content = open(file_path)
		generic_handle.save()

		if ds['ds_id'] != "HTML_FULL":
			# add HTML to self.html_concat
			fhand = open(file_path)
			html_parsed = BeautifulSoup(fhand)
			print "HTML document parsed..."
			#sets div with page_ID
			self.book_obj.html_concat = self.book_obj.html_concat + '<div id="page_ID_%s" class="html_page">' % (ds['order'])
			#Set in try / except block, as some HTML documents contain no elements within <body> tag
			try:
				for block in html_parsed.body:
					self.book_obj.html_concat = self.book_obj.html_concat + unicode(block)
			except:
				print "<body> tag is empty, skipping. Adding page_ID anyway."

			#closes page_ID / div
			self.book_obj.html_concat = self.book_obj.html_concat + "</div>"
			fhand.close()


	def processALTOXML(self, ds):
		print "Processing ALTO XML"
		file_path = self.book_obj.Bag.path + "/data/datastreams/" + ds['filename']
		print "Looking for:",file_path
		generic_handle = eulfedora.models.FileDatastreamObject(self.ohandle, 'ALTOXML', 'ALTOXML', mimetype=ds['mimetype'], control_group='M')
		generic_handle.label = 'ALTOXML'
		generic_handle.content = open(file_path)
		generic_handle.save()
		

	def sendAbbyyFiles(self):
		'''
		1) Send image to /tmp/abbyy/incoming/[PID]/IMAGE_[PAGE_NUM].[MIMETYPE]
		2) Wait for return?
		'''

		print "sending image file to abbyy for %s" % self.pid

		# open image handle
		image_handle = self.ohandle.getDatastreamObject('IMAGE')
		image_filename = '%s/%s%s' % (localConfig.ABBYY_INCOMING, self.pid.replace(":","_"), utilities.mimetypes.guess_extension(image_handle.mimetype))
		print image_filename

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
			print "OCR complete for %s" % self.pid
			return abbyy_output
		else:
			return False


	def updateAbbyyFiles(self, cleanup=True):

		'''update datastreams with abbyy output'''

		print "updating ABYYY files for %s" % self.pid

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
				print "updating HTML"
				ds_handle = self.ohandle.getDatastreamObject('HTML')
				ds_handle.content = fd.read()
				ds_handle.save()
			else:
				print "creating HTML datastream"
				ds_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "HTML", "HTML", mimetype="text/html", control_group='M')
				ds_handle.label = "HTML"
				ds_handle.content = fd.read()
				ds_handle.save()
		
		# TXT
		print "skipping txt for now..."
		
		# ALTOXML
		with open(abbyy_output['ALTOXML'],'r') as fd:
			if 'ALTOXML' in self.ohandle.ds_list:
				print "updating ALTOXML"
				ds_handle = self.ohandle.getDatastreamObject('ALTOXML')
				ds_handle.content = fd.read()
				ds_handle.save()
			else:
				print "creating ALTOXML datastream"
				ds_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "ALTOXML", "ALTOXML", mimetype="text/xml", control_group='M')
				ds_handle.label = "ALTOXML"
				ds_handle.content = fd.read()
				ds_handle.save()
		
		# PDF
		'''
		Will require updating full-text PDF
		'''
		print "skipping pdf for now..."


		# cleanup
		if cleanup:
			for k in abbyy_output:
				os.remove(abbyy_output[k])


	# regnerate derivative JP2s
	def regenJP2(self, regenIIIFManifest=False, target_ds=None, clear_cache=True):
		'''
		Function to recreate derivative JP2s based on JP2DerivativeMaker class in inc/derivatives
		Operates with assumption that datastream ID "FOO_JP2" is derivative as datastream ID "FOO"

		A lot are failing because the TIFFS are compressed, PNG files.  We need a secondary attempt
		that converts to uncompressed TIFF first.
		'''

		# iterate through datastreams and look for JP2s
		if target_ds is None:
			jp2_ds_list = [ ds for ds in self.ohandle.ds_list if self.ohandle.ds_list[ds].mimeType == "image/jp2" ]
		else:
			jp2_ds_list = [target_ds]

		for i, ds in enumerate(jp2_ds_list):

			print "converting %s, %s / %s" % (ds,str(i+1),str(len(jp2_ds_list)))

			# jp2 handle
			jp2_ds_handle = self.ohandle.getDatastreamObject(ds)

			# get original ds_handle
			print "for WSUebook_Page type, known original as 'IMAGE'"
			orig = 'IMAGE'
			try:
				orig_ds_handle = self.ohandle.getDatastreamObject(orig)
			except:
				print "could not find original for",orig

			# write temp original and set as inPath
			guessed_ext = utilities.mimetypes.guess_extension(orig_ds_handle.mimetype)
			print "guessed extension for temporary orig handle:",guessed_ext
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
				print "regenerating IIIF manifest"
				self.genIIIFManifest()

			if clear_cache:
				print "clearing cache"
				self.removeObjFromCache()

			return True



# helpers
'''
This might be where we can fix the gray TIFFs
'''
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





		




