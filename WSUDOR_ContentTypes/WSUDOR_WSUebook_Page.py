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
from WSUDOR_API.functions.packagedFunctions import singleObjectPackage

# derivatives
# from inc.derivatives import JP2DerivativeMaker
from inc import derivatives

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


	def processImage(self, ds):

		print "Processing derivative"
		file_path = self.book_obj.Bag.path + "/data/datastreams/" + ds['filename']
		print "Looking for:",file_path

		# original
		orig_handle = eulfedora.models.FileDatastreamObject(self.ohandle, 'IMAGE', 'IMAGE', mimetype=ds['mimetype'], control_group='M')
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

		# make JP2 with derivative class
		jp2_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "JP2", "JP2", mimetype="image/jp2", control_group='M')
		jp2_handle.label = "JP2"
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
		


	'''
	Consider methods / attributes for JP2, THUMBNAIL, ETC.
	'''


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





		




