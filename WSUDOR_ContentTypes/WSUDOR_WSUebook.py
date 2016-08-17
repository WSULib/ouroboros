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
import logging

# library for working with LOC BagIt standard
import bagit

# celery
from WSUDOR_Manager import celery

# eulfedora
import eulfedora

# WSUDOR
import WSUDOR_ContentTypes
from WSUDOR_Manager.solrHandles import solr_handle, solr_bookreader_handle
from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager import redisHandles, helpers, utilities
from WSUDOR_API.functions.packagedFunctions import singleObjectPackage

# localconfig
import localConfig

# import manifest factory instance
from inc.manifest_factory import iiif_manifest_factory_instance

# derivatives
from inc.derivatives import JP2DerivativeMaker


# helper function for natural sorting
def natural_sort_key(s, _nsre=re.compile('([0-9]+)')):
	return [int(text) if text.isdigit() else text.lower()
			for text in re.split(_nsre, s)]


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


	# pages from objMeta class
	@helpers.LazyProperty
	def pages_from_objMeta(self):

		'''
		Returns dictionary with order as key, list of assocated datastreams as val
		'''

		pages = defaultdict(list)
		for ds in self.objMeta['datastreams']:
			try:
				pages[int(ds['order'])].append(ds)
			except:
				print "Presented with 'order' attribute that was not integer, skipping..."
		return pages


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

		# check for tif, html, xml, and pdf files
		for page in self.pages_from_objMeta:
			if len(self.pages_from_objMeta[page]) < 4:
				report_failure(("Missing derivative filetypes","Page %d" % (page)))

		# finally, return verdict		
		return results_dict


	# ingest
	def ingestBag(self,indexObject=True):

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
				print "Writing relationship:",str(relationship['predicate']),str(relationship['object'])
				self.ohandle.add_relationship(str(relationship['predicate']),str(relationship['object']))

			# writes derived RELS-EXT
			# isRepresentedBy
			self.ohandle.add_relationship("http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isRepresentedBy",self.objMeta['isRepresentedBy'])

			# hasContentModel
			content_type_string = str("info:fedora/CM:"+self.objMeta['content_type'].split("_")[1])
			print "Writing ContentType relationship:","info:fedora/fedora-system:def/relations-external#hasContentModel",content_type_string
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


			########################################################################################################
			# iterate through pages and create page objects
			for page_num in self.pages_from_objMeta:
				page_dict = self.pages_from_objMeta[page_num]
				page_obj = WSUDOR_ContentTypes.WSUDOR_WSUebook_Page()
				page_obj.ingest(self, page_num)
			########################################################################################################


			# write generic thumbnail and preview
			rep_handle = eulfedora.models.DatastreamObject(self.ohandle, "THUMBNAIL", "THUMBNAIL", mimetype="image/jpeg", control_group="M")
			rep_handle.ds_location = "http://localhost/fedora/objects/%s_Page_%s/datastreams/THUMBNAIL/content" % (self.ohandle.pid, self.objMeta['isRepresentedBy'].split("_")[-1])
			rep_handle.label = "THUMBNAIL"
			rep_handle.save()

			# HTML (based on concatenated HTML from self.html_concat)
			if "HTML_FULL" not in [ds['ds_id'] for ds in self.objMeta['datastreams']]:
				html_full_handle = eulfedora.models.DatastreamObject(self.ohandle, "HTML_FULL", "Full HTML for item", mimetype="text/html", control_group="M")
				html_full_handle.label = "Full HTML for item"
				html_full_handle.content = self.html_concat.encode('utf-8')
				html_full_handle.save()

			# PDF - create PDF on disk and upload
			if "PDF_FULL" not in [ds['ds_id'] for ds in self.objMeta['datastreams']]:
				try:
					self.processPDF()
				except:					
					raise utilities.IngestError("Could not generate full-text pdf")

			# save and commit object before finishIngest()
			final_save = self.ohandle.save()

			# finish generic ingest
			# may pass methods here that will run in finishIngest()
			return self.finishIngest(gen_manifest=True, indexObject=indexObject, contentTypeMethods=[self.indexPageText])

		# exception handling
		except Exception,e:
			print traceback.format_exc()
			print "Ingest Error:",e
			return False


	# method to purge main book object and children pages
	def purgeConstituents(self):

		# purge children
		for page in self.pages_from_rels:
			page = self.pages_from_rels[page]
			print "purging:",page.label
			fedora_handle.purge_object(page)

		return True


	def processPDF(self, process_type='ingest', pdf_dir=None):

		# expecting pdf_dir if process_type != 'ingest'
		if process_type == 'ingest':
			obj_dir = self.Bag.path+"/data/datastreams"
		else:
			obj_dir = pdf_dir

		print "writing full-text PDF"
		temp_filename = "/tmp/Ouroboros/"+str(uuid.uuid4())+".pdf"
		os.system("pdftk %s/*.pdf cat output %s verbose" % (obj_dir, temp_filename))
		pdf_full_handle = eulfedora.models.DatastreamObject(self.ohandle, "PDF_FULL", "Fulltext PDF for item", mimetype="application/pdf", control_group='M')
		pdf_full_handle.label = "Fulltext PDF for item"
		pdf_full_handle.content = open(temp_filename).read()

		# remove pdf
		os.remove(temp_filename)

		return pdf_full_handle.save()


	# ingest image type
	def genIIIFManifest(self, on_demand=False):

		'''
		Currently generates IIIF manifest with one sequence, handful of canvases for each image.
		'''

		# Wait until risearch catches up with constituent objects
		print "waiting for risearch to catch up..."
		stime = time.time()
		ttime = 0
		while ttime < 30 :
			sparql_count = fedora_handle.risearch.sparql_count('select $page where  {{ $page <fedora-rels-ext:isConstituentOf> <info:fedora/%s> . }}' % (self.pid))
			print sparql_count
			if sparql_count < len(self.pages_from_objMeta):
				time.sleep(.5)
				continue
			else:
				print 'child objects in risearch, continuing'
				break

		# get solr_doc
		solr_doc = self.SolrDoc.asDictionary()

		# create root mani obj
		try:
			manifest = iiif_manifest_factory_instance.manifest( label=solr_doc['mods_title_ms'][0] )
		except:
			manifest = iiif_manifest_factory_instance.manifest( label="Unknown Title" )
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
				print "Could Not Set Metadata Field, Skipping",field_set[0]

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
			print "Working on:",page_handle.ohandle.label

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
			# HTML
			anno = annol.annotation()
			anno.text(ident="https://%s/WSUAPI/bitStream/%s/HTML" % (localConfig.APP_HOST, page_handle.pid), format="text/html")
			# ALTOXML
			anno = annol.annotation()
			anno.text(ident="https://%s/WSUAPI/bitStream/%s/ALTOXML" % (localConfig.APP_HOST, page_handle.pid), format="text/xml")

			# push annotationList to page object
			'''
			Automatically updates / overwrites
			'''
			print "Inserting annotation list for",page_handle.pid,"as object datastream..."
			ds_handle = eulfedora.models.DatastreamObject(page_handle.ohandle, "IIIF_ANNOLIST", "IIIF_ANNOLIST", mimetype="application/json", control_group="M")
			ds_handle.label = "IIIF_ANNOLIST"
			ds_handle.content = annol.toString()
			ds_handle.save()

		# create datastream with IIIF manifest and return JSON string
		print "Inserting manifest for",self.pid,"as object datastream..."
		ds_handle = eulfedora.models.DatastreamObject(self.ohandle, "IIIF_MANIFEST", "IIIF_MANIFEST", mimetype="application/json", control_group="M")
		ds_handle.label = "IIIF_MANIFEST"
		ds_handle.content = manifest.toString()
		ds_handle.save()

		return manifest.toString()


	def indexPageText(self):

		'''
		When copying objects between repositories, indexing of pages is skipped.
		This function can be run to repeat that process.
		'''

		for page in self.pages_from_rels:

			try:
				print "Working on page %d / %d" % (page, len(self.pages_from_rels))

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
				raise Exception("Could not index page %d" % page)

		# commit
		print solr_bookreader_handle.commit()



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

		print "generating virtual ScannedBook object"

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

		print "generating virtual ScannedVolume object"

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
		print "generating virtual ScannedPage object"

		for page_num in self.pages_from_rels:

			page_handle = WSUDOR_ContentTypes.WSUDOR_Object(self.pages_from_rels[page_num])
			virtual_page_handle = fedora_handle.get_object(type=WSUDOR_ContentTypes.WSUDOR_Readux_VirtualPage)
			virtual_page_handle.create(self, page_num, page_handle)


	def createReaduxVirtualObjects(self):

		self._createVirtBook()
		self._createVirtVolume()
		self._createVirtPages()


	def purgeReaduxVirtualObjects(self):

		sparql_response = fedora_handle.risearch.sparql_query('select $virtobj where  {{ $virtobj <http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isVirtualFor> <info:fedora/%s> . }}' % (self.pid))

		for obj in sparql_response:
			print "Purging virtual object: %s" % obj['virtobj']
			fedora_handle.purge_object( obj['virtobj'].split("info:fedora/")[-1] )

		return True


	def indexReaduxVirtualObjects(self, action='index'):

		'''
		NOTE: will need to wait here for risearch to index
		'''

		# index in Solr
		sparql_response = fedora_handle.risearch.sparql_query('select $virtobj where  {{ $virtobj <http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isVirtualFor> <info:fedora/%s> . }}' % (self.pid))

		for obj in sparql_response:
			print "Indexing object: %s" % obj['virtobj']
			print requests.get("http://localhost/ouroboros/solrReaduxDoc/%s/%s" % (obj['virtobj'].split("info:fedora/")[-1],action) ).content

		# generate TEI
		os.system('python /opt/readux/manage.py add_pagetei -u %s_Readux_VirtualVolume' % self.pid)

		return True

		
	def regenReaduxVirtualObjects(self):

		self.purgeReaduxVirtualObjects()

		time.sleep(1)

		self.createReaduxVirtualObjects()

		print "waiting for risearch to catch up..."
		while True:
			sparql_count = fedora_handle.risearch.sparql_count('select $virtobj where  {{ $virtobj <http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isVirtualFor> <info:fedora/%s> . }}' % (self.pid))
			if sparql_count < 1:
				time.sleep(.5)
				continue
			else:
				print 'proxy objects indexed in risearch, continuing'
				break

		self.indexReaduxVirtualObjects(action='index')

		
		














