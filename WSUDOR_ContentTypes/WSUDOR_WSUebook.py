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
import tempfile
import textract
from lxml import etree

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
from WSUDOR_Manager import models, solrHandles
from WSUDOR_Manager.solrHandles import solr_handle, solr_bookreader_handle
from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager.lmdbHandles import lmdb_env
from WSUDOR_Manager import redisHandles, helpers, utilities

# localconfig
import localConfig
from localConfig import *

# derivatives
# from inc.derivatives import JP2DerivativeMaker
from inc import derivatives


class WSUDOR_WSUebook(WSUDOR_ContentTypes.WSUDOR_GenObject):

	# static values for class
	label = "WSUeBook"
	description = "The WSUDOR_WSUebook content type models most print (but some born digital) resources we have created digital components for each page.  This includes a page image, ALTO XML with information about the location of words on the page, a thumbnail, a PDF (with embedded text), and HTML that semi-closely matches the original formatting (suitable for flowing text).  These objects are best viewed with our eTextReader."
	Fedora_ContentType = "CM:WSUebook"
	version = 3

	def __init__(self, object_type=False, content_type=False, payload=False,orig_payload=False):

		# run __init__ from parent class
		WSUDOR_ContentTypes.WSUDOR_GenObject.__init__(self,object_type, content_type, payload, orig_payload)

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

		# empty destinations for concatenated content
		self.html_concat = ''

		# content-type methods run and returned to API
		self.public_api_additions = [self.object_hierarchy]

		# OAIexposed (on ingest, register OAI identifier)
		self.OAIexposed = True


	# pages from objMeta class
	@helpers.LazyProperty
	def pages_from_objMeta(self):

		'''
		Returns dictionary with order as key, list of constituent objects
		'''

		pages = defaultdict(list)
		for constituent in self.objMeta['constituent_objects']:
			try:
				pages[int(constituent['order'])].append(constituent)
			except:
				logging.debug("Presented with 'order' attribute that was not integer, skipping...")
		return pages


	# pages from objMeta class
	@helpers.LazyProperty
	def pages_from_objMeta_v1(self):

		'''
		Returns dictionary with order as key, list of assocated datastreams as val
		'''

		pages = defaultdict(list)
		for ds in self.objMeta['datastreams']:
			try:
				pages[int(ds['order'])].append(ds)
			except:
				logging.debug("Presented with 'order' attribute that was not integer, skipping...")
		return pages


	# pages from objMeta class
	@helpers.LazyProperty
	def normalized_pages_from_objMeta(self):

		'''
		Returns dictionary with order as key, list of assocated datastreams as val, normalized to begin at one and not skip numbers
		'''

		count = 1
		if 'cover_placeholder' in self.objMeta.keys() and self.objMeta['cover_placeholder']:
			count += 1
		seq_pages = {}
		for page in self.pages_from_objMeta.keys():
			page_info = self.pages_from_objMeta[page]
			for ds in page_info:
				ds['order'] = count
			seq_pages[count] = page_info
			count += 1
		return seq_pages


	# MISSING pages from objMeta class
	@helpers.LazyProperty
	def missing_pages_from_objMeta(self):

		'''
		returns assumed missing pages based on numbering
		'''
		page_nums = self.pages_from_objMeta.keys()
		missing_pages_set = set(page_nums).symmetric_difference(xrange(page_nums[0], page_nums[-1] + 1))

		# add page 1 if not present
		if 1 not in missing_pages_set and 1 not in page_nums:
			missing_pages_set.add(1)

		return missing_pages_set


	# MISSING pages from normalized pages
	@helpers.LazyProperty
	def normalized_missing_pages_from_objMeta(self):

		'''
		returns assumed missing pages based on numbering
		'''
		page_nums = self.normalized_pages_from_objMeta.keys()
		missing_pages_set = set(page_nums).symmetric_difference(xrange(page_nums[0], page_nums[-1] + 1))

		# add page 1 if not present
		if 1 not in missing_pages_set and 1 not in page_nums:
			missing_pages_set.add(1)

		return missing_pages_set


	# pages from constituent objects
	@helpers.LazyProperty
	def pages_from_rels(self):

		'''
		Returns OrderedDict with pageOrder as key, digital obj as val
		'''

		# get ordered, constituent objs
		sparql_response = fedora_handle.risearch.sparql_query('select $page $pageOrder WHERE {{ $page <info:fedora/fedora-system:def/relations-external#isConstituentOf> <info:fedora/%s> .$page <http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/pageOrder> $pageOrder . }} ORDER BY ASC($pageOrder)' % (self.pid))
		constituent_objects = OrderedDict((int(page['pageOrder']), fedora_handle.get_object(page['page'])) for page in sparql_response)
		return constituent_objects


	# MISSING pages from rels relationships
	@helpers.LazyProperty
	def missing_pages_from_rels(self):

		'''
		returns assumed missing pages based on numbering
		'''
		page_nums = self.pages_from_rels.keys()
		missing_pages_set = set(page_nums).symmetric_difference(xrange(page_nums[0], page_nums[-1] + 1))

		# add page 1 if not present
		if not 1 in missing_pages_set:
			missing_pages_set.add(1)

		return missing_pages_set


	# congruency between expected pages in objMeta and actual page objects created
	@helpers.LazyProperty
	def missing_expected_pages(self):

		return set(self.missing_pages_from_rels) - set(self.missing_pages_from_objMeta)


	# method to return page that book is represented by
	@helpers.LazyProperty
	def representative_page(self):
		try:
			page_num = int(self.objMeta['isRepresentedBy'].split("_")[-1])
			return self.pages_from_rels[page_num]
		except:
			logging.debug("could not determine representative page, defaulting page 1")
			return self.pages_from_rels[1]


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
			report_failure(("Valid ContentType","WSUDOR_Object instance's ContentType: %s, not found in acceptable ContentTypes: %s " % (self.content_type, WSUDOR_ContentTypes.WSUDOR_GenObject.__subclasses__())))

		# check for tif, html, xml, and pdf files
		# for page in self.pages_from_objMeta:
		# 	if len(self.pages_from_objMeta[page]) < 4:
		# 		report_failure(("Missing derivative filetypes","Page %d" % (page)))

		# finally, return verdict		
		return results_dict


	# ingest
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

			# write explicit RELS-EXT relationships from object_relationships in objMeta
			for relationship in self.objMeta['object_relationships']:
				logging.debug("Writing relationship: %s %s" % (str(relationship['predicate']),str(relationship['object'])))
				self.ohandle.add_relationship(str(relationship['predicate']),str(relationship['object']))

			# writes derived RELS-EXT
			# isRepresentedBy
			'''
			if present, isRepresentedBy relationship from objMeta trumps pre-existing relationships
			'''
			if 'isRepresentedBy' in self.objMeta.keys():
				# purge old ones
				for s,p,o in self.ohandle.rels_ext.content:
					if str(p) == 'http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isRepresentedBy':
						logging.debug('found pre-existing isRepresentedBy relationship, %s, removing as we have one from objMeta' % str(o))
						self.ohandle.purge_relationship('http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isRepresentedBy',o)
				logging.debug("writing isRepresentedBy from objMeta: %s" % self.objMeta['isRepresentedBy'])
				self.ohandle.add_relationship("http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isRepresentedBy",self.objMeta['isRepresentedBy'])

			# hasContentModel
			content_type_string = str("info:fedora/CM:"+self.objMeta['content_type'].split("_")[1])
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


			# PAGES
			########################################################################################################
			# iterate through anticipated missing pages and create missing page objects
			# for page_num in self.normalized_missing_pages_from_objMeta:
			# 	page_obj = WSUDOR_ContentTypes.WSUDOR_WSUebook_Page()
			# 	page_obj.ingestMissingPage(self, page_num)
				
			# iterate through pages and create page objects
			for obj in self.constituents_from_objMeta:

				# try untarred directory first
				target_bag = "/".join([self.temp_payload, 'data', 'constituent_objects', obj['directory']])
				if os.path.exists(target_bag):
					logging.debug('constituent bag found, using')
				# if directory not found, might be tar file, check for this
				else:
					target_bag = "/".join([self.temp_payload, 'data', 'constituent_objects', "%s.tar" % obj['directory']])
					if os.path.exists(target_bag):
						logging.debug('constituent tarred bag found, using')
					# if neither, raise exception
					else:
						logging.debug('could not find constituent directory or tar file, skipping')
						raise Exception('constituent bag not found')

				logging.debug('ingesting constituent object %s' % target_bag)
				constituent_bag = WSUDOR_ContentTypes.WSUDOR_Object(target_bag, object_type='bag')
				constituent_bag.ingest(indexObject=True)
			########################################################################################################

			# write generic thumbnail and preview
			logging.debug("writing generic thumb and preview")
			rep_handle = eulfedora.models.DatastreamObject(self.ohandle, "THUMBNAIL", "THUMBNAIL", mimetype="image/jpeg", control_group="M")
			rep_page_num = int(self.objMeta['isRepresentedBy'].split("_")[-1])
			if "cover_placeholder" in self.objMeta and self.objMeta['cover_placeholder']:
				rep_page_num += 1
			rep_handle.ds_location = "http://localhost/fedora/objects/%s_Page_%s/datastreams/THUMBNAIL/content" % (self.ohandle.pid, rep_page_num)
			rep_handle.label = "THUMBNAIL"
			rep_handle.save()

			# full book HTML
			'''
			Derive fullbook HTML
			'''
			HTML_search = [ ds for ds in self.objMeta['datastreams'] if ds['ds_id'] == 'HTML_FULL' ]
			if len(HTML_search) > 0:
				logging.debug('HTML_FULL found in objMeta, ingesting')
				ds = HTML_search[0]
				ds_handle = eulfedora.models.DatastreamObject(self.ohandle, ds['ds_id'], ds['label'], mimetype=ds['mimetype'], control_group="M")
				ds_handle.label = ds['label']
				file_path = self.Bag.path + "/data/datastreams/" + ds['filename']
				logging.debug("looking for path: %s" % file_path)
				logging.debug(os.path.exists(file_path))
				ds_handle.content = open(file_path).read()
				ds_handle.save()
			else:	
				try:
					self.processHTML(update_objeMeta=True)
				except:
					logging.debug("could not process HTML")

			# EPUB
			'''
			Determine if ebook comes with an EPUB file
			'''
			EPUB_search = [ ds for ds in self.objMeta['datastreams'] if ds['ds_id'] == 'EPUB' ]
			if len(EPUB_search) > 0:
				logging.debug('EPUB found in objMeta, ingesting')
				ds = EPUB_search[0]
				ds_handle = eulfedora.models.DatastreamObject(self.ohandle, ds['ds_id'], ds['label'], mimetype=ds['mimetype'], control_group="M")
				ds_handle.label = ds['label']
				file_path = self.Bag.path + "/data/datastreams/" + ds['filename']
				logging.debug("looking for path: %s" % file_path)
				logging.debug(os.path.exists(file_path))
				ds_handle.content = open(file_path).read()
				ds_handle.save()
			else:	
				logging.debug("could not find EPUB")
					
			# full book PDF
			'''
			Due to various ingest methods, some books will contain PDF files for each page, and some may not.
			As a result, we always export the PDF_FULL if possible and include in the bag, but do not update the objMeta.json.
			If the file is not present, we attempt to processPDF for the first time
			'''
			PDF_search = [ ds for ds in self.objMeta['datastreams'] if ds['ds_id'] == 'PDF_FULL' ]
			if len(PDF_search) > 0:
				logging.debug('PDF_FULL found in objMeta, ingesting')
				ds = PDF_search[0]
				ds_handle = eulfedora.models.DatastreamObject(self.ohandle, ds['ds_id'], ds['label'], mimetype=ds['mimetype'], control_group="M")
				ds_handle.label = ds['label']
				file_path = self.Bag.path + "/data/datastreams/" + ds['filename']
				logging.debug("looking for path: %s" % file_path)
				logging.debug(os.path.exists(file_path))
				ds_handle.content = open(file_path).read()
				ds_handle.save()
			else:	
				try:
					self.processPDF(update_objeMeta=True)
				except:
					logging.debug("could not process PDF")
			
			# save and commit object before finishIngest()
			final_save = self.ohandle.save()

			# finish generic ingest
			# may pass methods here that will run in finishIngest()
			return self.finishIngest(gen_manifest=True, indexObject=indexObject, contentTypeMethods=[])

		# exception handling
		except Exception,e:
			logging.debug("%s" % traceback.format_exc())
			logging.debug("Ingest Error: %s" % e)
			return False


	# create missing page objects
	def genMissingPages(self, reindex=True):
		
		for page_num in self.missing_pages_from_objMeta:
			logging.debug("Generating missing page: %s" % page_num)
			page_obj = WSUDOR_ContentTypes.WSUDOR_WSUebook_Page()
			page_obj.ingestMissingPage(self, page_num, from_bag=False)

		# reindex book
		self.refresh()


	# method to purge main book object and children pages
	def purgeConstituents(self):

		# purge children
		for page in self.pages_from_rels:
			try:
				page = self.pages_from_rels[page]
				logging.debug("purging constituent: %s" % page.label)
				obj = WSUDOR_ContentTypes.WSUDOR_Object(page.pid)
				obj.purge(override_state=True)
			except:
				logging.debug("could not remove constituent: %s" % page)

		return True


	def processHTML(self, process_type='ingest', update_objeMeta=False):

		logging.debug("Processing HTML for entire book...")
		
		# iterate over constituent_objects
		for obj in self.constituents_from_objMeta:

			# derive file_path of HTML
			for ds in obj['datastreams']:
				if ds['ds_id'] == 'HTML':
					file_path = "/".join([self.temp_payload, 'data', 'constituent_objects', obj['directory'], 'data', 'datastreams', ds['filename']])
			
			# add HTML to self.html_concat
			fhand = open(file_path)
			html_parsed = BeautifulSoup(fhand)
			logging.debug("HTML document parsed...")
			#sets div with page_ID
			self.html_concat = self.html_concat + '<div id="page_ID_%s" class="html_page">' % (obj['order'])
			#Set in try / except block, as some HTML documents contain no elements within <body> tag
			try:
				for block in html_parsed.body:
					self.html_concat = self.html_concat + unicode(block)
			except:
				logging.debug("<body> tag is empty, skipping. Adding page_ID anyway.")

			#closes page_ID / div
			self.html_concat = self.html_concat + "</div>"
			fhand.close()

		# write to datastream
		html_full_handle = eulfedora.models.DatastreamObject(self.ohandle, "HTML_FULL", "Full HTML for item", mimetype="text/html", control_group="M")
		html_full_handle.label = "Full HTML for item"
		html_full_handle.content = self.html_concat.encode('utf-8')
		html_full_handle.save()

		# update objMeta
		if update_objeMeta:
			self.objMeta['datastreams'].append({
				'mimetype': "text/html",
				'label': "Full HTML for item",
				'ds_id': "HTML_FULL",
				'internal_relationships': { },
				'filename': "HTML_FULL.htm"
				}
			)
		self.update_objMeta()

	
	def processPDF(self, process_type='ingest', pdf_dir=None, update_objeMeta=False):

		# expecting pdf_dir if process_type != 'ingest'
		if process_type == 'ingest':
			obj_dir = self.Bag.path
		else:
			obj_dir = pdf_dir

		logging.debug("writing full-text PDF")
		temp_filename = "/tmp/Ouroboros/"+str(uuid.uuid4())+".pdf"
		os.system("pdftk `find -L %s -name '*.pdf' | awk -vFS=/ -vOFS=/ '{ print $NF,$0 }' | sort -n -t / | cut -f2- -d/ | xargs echo` cat output %s verbose" % (obj_dir, temp_filename))
		pdf_full_handle = eulfedora.models.DatastreamObject(self.ohandle, "PDF_FULL", "Fulltext PDF for item", mimetype="application/pdf", control_group='M')
		pdf_full_handle.label = "Fulltext PDF for item"
		pdf_full_handle.content = open(temp_filename).read()

		# remove pdf
		os.remove(temp_filename)

		# update objMeta
		if update_objeMeta:
			self.objMeta['datastreams'].append({
				'mimetype': "application/pdf",
				'internal_relationships': { },
				'ds_id': "PDF_FULL",
				'label': "PDF_PDF_FULL",
				'filename': "PDF_FULL.pdf"
				}
			)
		self.update_objMeta()

		return pdf_full_handle.save()


	# ingest image type
	def genIIIFManifest(self, on_demand=False, create_page_annotation_list=False, attempt_remote_retrieval=localConfig.ATTEMPT_REMOTE):

		'''
		Currently generates IIIF manifest with one sequence, handful of canvases for each image.
		'''

		# attempt retrieval
		if attempt_remote_retrieval:
			manifest = self.retrieveIIIFManifest()
			if manifest:
				logging.debug('found remote IIIF manifest, using!')
				return manifest

		# Wait until risearch catches up with constituent objects
		logging.debug("waiting for risearch to catch up...")
		stime = time.time()
		ttime = 0
		while ttime < 30 :
			sparql_count = fedora_handle.risearch.sparql_count('select $page where  {{ $page <fedora-rels-ext:isConstituentOf> <info:fedora/%s> . }}' % (self.pid))
			logging.debug("%s" % sparql_count)
			if sparql_count < len(self.pages_from_objMeta):
				time.sleep(.5)
				ttime = time.time() - stime
				logging.debug("%s" % ttime)
				continue
			else:
				logging.debug('constituent objects found in risearch, continuing')
				break

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
				manifest.set_metadata({ field_set[0] : eval(field_set[1]) })
			except:
				logging.debug("Could Not Set Metadata Field, Skipping %s" % field_set[0])

		# start anonymous sequence
		seq = manifest.sequence(label="default sequence")

		# write constituent pages
		'''
		This is tricky.
		When ingesting new objects, the rels-ext relationships are written at a slight delay.
		As such, without waiting / confirming all relationships are indexed in risearch,
		results in only subsets of the whole book getting added.
		'''

		# self.pages_from_rels
		for page_num in self.pages_from_rels:			

			# open wsudor handle
			page_handle = WSUDOR_ContentTypes.WSUDOR_Object(self.pages_from_rels[page_num])
			logging.debug("Working on: %s" % page_handle.ohandle.label)

			# generate obj|ds self.pid as defined in loris TemplateHTTP extension
			fedora_http_ident = "fedora:%s|JP2" % (page_handle.pid)

			# Instantiate canvas under sequence
			cvs = seq.canvas(ident=fedora_http_ident, label=page_handle.ohandle.label)

			# Create an annotation on the Canvas
			anno = cvs.annotation()

			# Add Image Annotation
			img = anno.image(fedora_http_ident, iiif=True)
			img.id = fedora_http_ident
			img.set_hw_from_iiif()

			# set canvas dimensions
			cvs.height = img.height
			cvs.width = img.width

			# create annotationsList for page object
			annol = cvs.annotationList("%s" % (page_handle.pid))

			# create annotations for HTML and ALTOXML content
			if create_page_annotation_list:
				# HTML
				anno = annol.annotation()
				anno.text(ident="https://%s/WSUAPI/bitStream/%s/HTML" % (localConfig.APP_HOST, page_handle.pid), format="text/html")
				# ALTOXML
				anno = annol.annotation()
				anno.text(ident="https://%s/WSUAPI/bitStream/%s/ALTOXML" % (localConfig.APP_HOST, page_handle.pid), format="text/xml")

				# save annotationList to LMDB database
				logging.debug("Saving annotation list for %s in LMDB database" % page_handle.pid)
				models.LMDBClient.put('%s_iiif_annotation_list' % page_handle.pid, annol.toString(), overwrite=True)

		# save manifest to LMDB database
		logging.debug("Saving manifest for %s in LMDB database" % self.pid)
		models.LMDBClient.put('%s_iiif_manifest' % self.pid, manifest.toString(), overwrite=True)

		return manifest.toString()


	def indexPagesText(self):

		'''
		When copying objects between repositories, indexing of pages is skipped.
		This function can be run to repeat that process.
		'''

		for page in self.pages_from_rels:

			try:
				logging.debug("Working on page %d / %d" % (page, len(self.pages_from_rels)))

				# index in Solr bookreader core
				data = {
					"literal.id" : self.objMeta['identifier']+"_OCR_HTML_"+str(page),
					"literal.ItemID" : self.objMeta['identifier'],
					"literal.page_num" : page,
					"fmap.content" : "OCR_text",
					"commit" : "false"
				}
				ds_handle = fedora_handle.get_object("%s_Page_%d" % (self.pid, page)).getDatastreamObject("HTML")
				files = {'file': ds_handle.content}
				r = requests.post("http://localhost/solr4/bookreader/update/extract", data=data, files=files)
			except:
				logging.debug("Could not index page %d" % page)

		# commit
		logging.debug("%s" % solr_bookreader_handle.commit())


	# method to regenerate full-text HTML
	def regenFullHTML(self):

		'''
		Some books were created mis-ordered HTML pages for the HTML_FULL datastream.
		This utility recreates HTML_FULL, leveraging self.html_concat
		'''

		# iterarte through pages
		for page_num in self.pages_from_rels:
			page = self.pages_from_rels[page_num]
			logging.debug("working on %s" % page)
			html_handle = page.getDatastreamObject('HTML')
			html_parsed = BeautifulSoup(html_handle.content)
			logging.debug("HTML document parsed...")
			#sets div with page_ID
			self.html_concat = self.html_concat + '<div id="page_ID_%s" class="html_page">' % (page_num)
			#Set in try / except block, as some HTML documents contain no elements within <body> tag
			try:
				for block in html_parsed.body:
					self.html_concat = self.html_concat + unicode(block)
			except:
				logging.debug("<body> tag is empty, skipping. Adding page_ID anyway.")

			#closes page_ID / div
			self.html_concat = self.html_concat + "</div>"

		# HTML (based on concatenated HTML from self.html_concat)
		logging.debug("Saving new, ordered HTML_FULL")
		html_full_handle = eulfedora.models.DatastreamObject(self.ohandle, "HTML_FULL", "Full HTML for item", mimetype="text/html", control_group="M")
		html_full_handle.label = "Full HTML for item"
		html_full_handle.content = self.html_concat.encode('utf-8')
		html_full_handle.save()
		return html_full_handle


	def regenAbbyyFiles(self, sendFiles=True, checkFiles=True, updateFiles=True):
		
		'''
		1) iterate through pages, fire off page images to Abbyy
		2) poll for ALL page images to finish
		'''
		stime = time.time()
		pages_from_rels = self.pages_from_rels.copy()

		if sendFiles:
			# fire off page images to Abbyy
			logging.debug("sending files to Abbyy")
			for page_num in pages_from_rels:
				page = WSUDOR_ContentTypes.WSUDOR_Object(pages_from_rels[page_num])
				page.sendAbbyyFiles()

		if checkFiles:
			# poll for finished OCR process
			ocr_list = []
			logging.debug("polling for OCR process to complete")
			while len(pages_from_rels) > 0:			
				for page_num in pages_from_rels:
					page = WSUDOR_ContentTypes.WSUDOR_Object(pages_from_rels[page_num])
					page_ocr = page.checkAbbyyFiles()
					if page_ocr:
						# add to list				
						ocr_list[1:1] = page_ocr
						# pop from dictionary
						del pages_from_rels[page_num]
					if len(pages_from_rels) == 0:
						break
				else:
					logging.debug("time elapsed %s" % str(time.time()-stime))
					time.sleep(5)

		if updateFiles:
			# update datastreams
			pages_from_rels = self.pages_from_rels.copy()
			for page_num in pages_from_rels:
				page = WSUDOR_ContentTypes.WSUDOR_Object(pages_from_rels[page_num])
				page.updateAbbyyFiles(cleanup=True)

		# finis
		logging.debug("total time elapsed: %s seconds" % str(time.time()-stime))
		return True


	# create dictionary comprehensive of all associated images
	def previewImage(self):

		'''
		Return image/loris params for API to render
			- pid, datastream, region, size, rotation, quality, format
		'''

		# get page represented by
		page = self.representative_page
		
		return (page.pid, 'JP2', 'full', '!960,960', 0, 'default', 'jpg')


	def index_augment(self):

		# get ds content
		ds_handle = self.ohandle.getDatastreamObject("HTML_FULL")
		ds_content = ds_handle.content
		
		# assume v1 book, attempt ds_content again
		if ds_content == None:

			# derive fullbook PID	
			self.ohandle = fedora_handle.get_object(PID.split(":")[1]+":fullbook")
			ds_handle = self.ohandle.getDatastreamObject("HTML_FULL")
			ds_content = ds_handle.content

		# use Solr's Tika Extract to strip down to text
		baseurl = "http://localhost/solr4/fedobjs/update/extract?&extractOnly=true"
		files = {'file': ds_content}		
		r = requests.post(baseurl, files=files)
		ds_stripped_content = r.text	

		# add to solr doc
		self.SolrDoc.doc.int_fullText = ds_stripped_content

		# index each page's full text for bookreader core
		logging.debug("running page indexer")
		self.indexPagesText()


	# content_type refresh
	def refresh_content_type(self):

		# regen IIIF manifest
		self.genIIIFManifest()

		# regen Readux objects
		# self.regenReaduxVirtualObjects()


	def export_constituents(self, objMeta, bag_root, data_root, datastreams_root, tarball, preserve_relationships, overwrite_export):

		# if not exist, create /constituent_objects directory
		if not os.path.exists("/".join([bag_root, 'data', 'constituent_objects'])):
			logging.debug("creating /constituent_objects dir")
			os.mkdir("/".join([bag_root, 'data', 'constituent_objects']))

		# itererate through constituents and export
		for obj in self.constituents:
			logging.debug('exporting %s' % obj.pid)
			constituent = WSUDOR_ContentTypes.WSUDOR_Object(obj.pid)
			constituent.export(
				export_dir="/".join([bag_root, 'data', 'constituent_objects']),
				tarball=tarball,
				preserve_relationships=preserve_relationships,
				overwrite_export=overwrite_export)


	def export_content_type(self, objMeta, bag_root, data_root, datastreams_root, tarball, preserve_relationships, overwrite_export):

		# export constituents
		self.export_constituents(objMeta, bag_root, data_root, datastreams_root, tarball, preserve_relationships, overwrite_export)


	def extract_raw_text(self, save_to_object=True, page_list=None):

		'''
		Method to extract raw text from book
			- sets TEXT datasteram with raw text
			- sets TEI datastream with raw text as minimally encoded TEI
		'''

		# extract		
		page_text_dict = self._extract_text_altoxml(page_list=page_list)

		# concatenate pages as raw text
		raw_text = '\n'.join([ text for num,text in page_text_dict.items() ])

		# store as datastream
		if raw_text != None and save_to_object:
			logging.debug('write raw text to TEXT datastream')			
			text_handle = eulfedora.models.DatastreamObject(self.ohandle, 'TEXT', 'TEXT', mimetype='text/plain', control_group="M")
			text_handle.label = 'TEXT'						
			text_handle.content = raw_text
			text_handle.save()

		# encode as TEI
		tei = self._encode_raw_text_as_tei(page_text_dict)

		# store as datastream
		if tei != None and save_to_object:
			logging.debug('write TEI to TEI datastream')			
			text_handle = eulfedora.models.DatastreamObject(self.ohandle, 'TEI', 'TEI', mimetype='text/xml', control_group="M")
			text_handle.label = 'TEI'						
			text_handle.content = tei
			text_handle.save()

		# return
		return (raw_text, tei)


	def _extract_text_altoxml(self, page_list=None):

		'''
		Method to extract raw text from ALTOXML datastreams for each page
		inspiried by Readux: https://github.com/ecds/readux/blob/50a895dcf7d64b753a07808e9be218cab3682850/readux/books/models.py#L448-L459

		Returns:
			(OrderedDict): {pagenum (int):rawtext (str)},...
		'''

		logging.debug('extract raw text for %s via ALTOXML' % self.pid)

		# prepare list of pages to work on
		pages = self.pages_from_rels.items()			
		if page_list:			
			pages = [ (page_num, pages[page_num][1]) for page_num in page_list ]

		# set local blank fulltext
		page_text_dict = OrderedDict()

		# loop through constituents, adding raw text to dictionary
		for num, page in pages:
			
			if 'ALTOXML' in page.ds_list.keys():

				logging.debug('extracting text from page %s' % num)

				# retrieve and parse with BS4
				xmlsoup = BeautifulSoup(page.getDatastreamObject('ALTOXML').content.serialize())

				# get page text
				page_text = '\n'.join((' '.join(s['content'] for s in line.find_all('string'))) for line in xmlsoup.find_all('textline'))

				# append to object
				page_text_dict[num] = page_text

		return page_text_dict


	def _extract_text_pdf(self, method='pdfminer'):

		logging.debug('extract raw text for %s via PDF text extraction' % self.pid)

		# if has full PDF
		if 'PDF_FULL' in self.ohandle.ds_list.keys():

			# create temp file
			f = tempfile.mkstemp(suffix='.pdf')

			# write PDF to temp file
			with open(f[1], 'wb') as f_handle:
				f_handle.write(self.ohandle.getDatastreamObject('PDF_FULL').content)

			# parse with textract
			book_text = textract.process(f[1], method=method)

			# if pdfminer used, tendency to include double blank spaces, and trailing whitespace
			# 	- convert doubles to singles, and rstrip
			if method == 'pdfminer':
					logging.debug('making adjustments for pdfminer parser')
					book_text = book_text.replace('  ',' ')
					book_text = book_text.replace(' \n','\n')

			# remove tempfile
			os.remove(f[1])		

		return book_text


	def _encode_raw_text_as_tei(self, page_text_dict):

		'''
		Method to encode paginated raw text as simple TEI
		'''

		# init root node
		tei_root = etree.Element('TEI', nsmap={
			'tei':'http://www.tei-c.org/ns/1.0',
			'xs':'http://www.w3.org/2001/XMLSchema'
		})

		# set attributes		
		tei_root.set('xmlns','http://www.tei-c.org/ns/1.0')

		# init and append header
		teiHeader = etree.fromstring('''<teiHeader>
	<fileDesc>
		<titleStmt>
			<title> </title>
		</titleStmt>
		<publicationStmt>
			<idno> </idno>
		</publicationStmt>       
		<sourceDesc>
			<bibl> </bibl>
		</sourceDesc>
	</fileDesc>
</teiHeader>''')
		tei_root.append(teiHeader)		

		# init text and body node
		text = etree.SubElement(tei_root, 'text')		
		body = etree.SubElement(text, 'body')		

		# loop through pages and write as <div>s
		for num, page_text in page_text_dict.items():

			# bump num
			num = num + 1
			
			# init div
			div = etree.Element('div')
			div.set('type','page')
			div.set('n','%s' % num)

			# init p_image
			pb = etree.Element('pb')
			pb.set('n','%s' % num)
			pb.set('facs','https://digidev3.library.wayne.edu/loris/fedora:%s_Page_%s|JP2/full/,1700/0/default.jpg' % (self.pid, num))
			div.append(pb)
			
			# init p_text
			try:			
				encoded_page_text = page_text.replace("\n","<lb/>")
				p_text = etree.fromstring('<p>%s</p>' % encoded_page_text)			
			except:
				p_text = etree.Element('p')
			div.append(p_text)

			# attach			
			body.append(div)

		# return serialized
		return etree.tostring(tei_root)



	def raw_text(self):

		'''
		Return raw text for book
			- if datastream does not exist, attempt to extract, save, and return
		'''

		if 'TEXT' in self.ohandle.ds_list.keys() and 'TEI' in self.ohandle.ds_list.keys():
			text_handle = self.ohandle.getDatastreamObject('TEXT')
			tei_handle = self.ohandle.getDatastreamObject('TEI')
			return (text_handle.content, tei_handle.content.serialize())

		else:
			raw_text_output = self.extract_raw_text()
			return raw_text_output


	# def extract_page_range_raw_text(self, page_list):

	# 	'''
	# 	Method to extract raw text from ALTOXML
	# 	'''

	# 	# return page text from ALTOXML
	# 	return self._extract_text_altoxml(page_list=page_list)






	#############################################################################
	# associated Readux style virtual objects
	#############################################################################

	'''
	Notes

	Setting up Book via Readux models (works from Django shell `python manage.py shell`):
	b = books.models.Book('wayne:FooBar_vBook')
	b.pid = 'wayne:FooBar_vBook'

	But then immdiately get affordances of readux models:
	In [13]: b.get_absolute_url()
	Out[13]: u'/books/wayne:FooBar_vBook/'

	'''

	# create Book Object (e.g. emory:b5hnv)
	def _createVirtBook(self):

		'''
		Target Datastreams:
			- DC
				- text/xml
			MARCXML
				- text/xml
			RELS-EXT
				- application/rdf+xml
		'''

		logging.debug("generating virtual ScannedBook object")

		virtual_book_handle = fedora_handle.get_object(type=WSUDOR_ContentTypes.WSUDOR_Readux_VirtualBook)
		virtual_book_handle.create(self)


	def _createVirtVolume(self):
		'''
		Target Datastreams:
			- DC
				- text/xml
			- OCR
				- text/xml
			- PDF
				- application/pdf
			- RELS-EXT
				- applicaiton/rdf+xml
		'''

		logging.debug("generating virtual ScannedVolume object")

		virtual_volume_handle = fedora_handle.get_object(type=WSUDOR_ContentTypes.WSUDOR_Readux_VirtualVolume)
		virtual_volume_handle.create(self)


	def _createVirtPages(self):
		'''
		Target Datastreams:
			- text
				- application/x-empty
			- DC
				- text/xml
			- position
				- text/plain
			- source-image
				- image/jp2
			- text
				- text/xml
			- RELS-EXT
				- applicaiton/rdf+xml
		'''
		logging.debug("generating virtual ScannedPage object")

		for page_num in self.pages_from_rels:

			page_handle = WSUDOR_ContentTypes.WSUDOR_Object(self.pages_from_rels[page_num])
			virtual_page_handle = fedora_handle.get_object(type=WSUDOR_ContentTypes.WSUDOR_Readux_VirtualPage)
			virtual_page_handle.create(self, page_num, page_handle)


	def createReaduxVirtualObjects(self):

		self._createVirtBook()
		self._createVirtVolume()
		self._createVirtPages()


	def purgeReaduxVirtualObjects(self):

		readux_solr_handle = solrHandles.onDemand('readux')

		sparql_response = fedora_handle.risearch.sparql_query('select $virtobj where  {{ $virtobj <http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isVirtualFor> <info:fedora/%s> . }}' % (self.pid))

		for obj in sparql_response:
			logging.debug("Purging virtual object: %s" % obj['virtobj'])
			fedora_handle.purge_object( obj['virtobj'].split("info:fedora/")[-1] )
			logging.debug("Removing from Readux solr core...")
			readux_solr_handle.delete_by_key(obj['virtobj'].split("info:fedora/")[-1], commit=False)

		# commit solr purges
		readux_solr_handle.commit()

		return True


	def indexReaduxVirtualObjects(self, action='index'):

		'''
		NOTE: will need to wait here for risearch to index
		'''

		# index in Solr
		sparql_response = fedora_handle.risearch.sparql_query('select $virtobj where  {{ $virtobj <http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isVirtualFor> <info:fedora/%s> . }}' % (self.pid))

		for obj in sparql_response:
			logging.debug("Indexing object: %s" % obj['virtobj'])
			index_url = "http://localhost/ouroboros/solrReaduxDoc/%s/%s" % (obj['virtobj'].split("info:fedora/")[-1],action) 
			logging.debug("%s" % index_url)
			logging.debug("%s" % requests.get(index_url).content)

		# generate TEI
		TEI_result = self.generateTEI()

		return True


	def generateTEI(self):
		logging.debug("generating TEI...")
		try:
			return os.system('/usr/local/lib/venvs/ouroboros/bin/python /opt/readux/manage.py add_pagetei -u %s_Readux_VirtualVolume' % self.pid)
		except:
			logging.debug("Could not generate TEI")
			return False


		
	def regenReaduxVirtualObjects(self):

		self.purgeReaduxVirtualObjects()

		time.sleep(1)

		self.createReaduxVirtualObjects()

		logging.debug("waiting for risearch to catch up...")
		while True:
			sparql_count = fedora_handle.risearch.sparql_count('select $virtobj where  {{ $virtobj <http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isVirtualFor> <info:fedora/%s> . }}' % (self.pid))
			if sparql_count < 1:
				time.sleep(.5)
				continue
			else:
				logging.debug('proxy objects indexed in risearch, continuing')
				break

		self.indexReaduxVirtualObjects(action='index')




		
		













