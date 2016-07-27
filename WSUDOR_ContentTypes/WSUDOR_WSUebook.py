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
				self.processPDF()

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
			("Item URL", "\"<a href='%s'>%s</a>\" % (single_json['objectSolrDoc']['mods_location_url_ms'][0],single_json['objectSolrDoc']['mods_location_url_ms'][0])"),
			("Original", "single_json['objectSolrDoc']['mods_otherFormat_note_ms'][0]")
		]
		for field_set in preferred_fields:
			try:
				manifest.set_metadata({ field_set[0]:eval(field_set[1]) })
			except:
				print "Could Not Set Metadata Field, Skipping",field_set[0]

		# start anonymous sequence
		seq = manifest.sequence(label="default sequence")

		# write constituent pages
		for page in self.pages_from_rels:

			# open wsudor handle
			page_handle = WSUDOR_ContentTypes.WSUDOR_Object(self.pages_from_rels[page])
			print "Working on:",page_handle.ohandle.label

			# generate obj|ds self.pid as defined in loris TemplateHTTP extension
			fedora_http_ident = "fedora:%s_Page_%d|JP2" % (self.pid, page_handle.order)

			# Create a canvas with uri slug of page-1, and label of Page 1
			cvs = seq.canvas(ident=fedora_http_ident, label=page_handle.ohandle.label)

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


	def indexPageText(self):

		'''
		When copying objects between repositories, indexing of pages is skipped.
		This function can be run to repeat that process.
		'''

		for page in self.pages_from_rels:
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


		# get pages
		sparql_response = fedora_handle.risearch.sparql_query('select $primary_image $order WHERE {{ $primary_image <info:fedora/fedora-system:def/relations-internal#isPartOf> <info:fedora/%s> . $primary_image <info:fedora/fedora-system:def/relations-internal#isOrder> $order . }} ORDER BY ASC($order)' % (self.pid))

		for page in sparql_response:

			print page

			virtual_page_handle = fedora_handle.get_object(type=WSUDOR_ContentTypes.WSUDOR_Readux_VirtualPage)
			virtual_page_handle.create(self,page)


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


	def indexReaduxVirtualObjects(self,action='index'):

		'''
		NOTE: will need to wait here for risearch to index
		'''

		sparql_response = fedora_handle.risearch.sparql_query('select $virtobj where  {{ $virtobj <http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isVirtualFor> <info:fedora/%s> . }}' % (self.pid))

		for obj in sparql_response:
			print "Indexing object: %s" % obj['virtobj']
			print requests.get("http://localhost/ouroboros/solrReaduxDoc/%s/%s" % (obj['virtobj'].split("info:fedora/")[-1],action) ).content

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



# # helpers
# '''
# This might be where we can fix the gray TIFFs
# '''
# def imMode(im):
# 	# check for 16-bit tiffs
# 	print "Image mode:",im.mode
# 	if im.mode in ['I;16','I;16B']:
# 		print "I;16 tiff detected, converting..."
# 		im.mode = 'I'
# 		im = im.point(lambda i:i*(1./256)).convert('L')
# 	# else if not RGB, convert
# 	elif im.mode != "RGB" :
# 		print "Converting to RGB"
# 		im = im.convert("RGB")

# 	return im
