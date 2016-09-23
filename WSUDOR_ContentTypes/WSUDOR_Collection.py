# module for management of bags in the WSUDOR environment
import bagit
import os
import mimetypes
import json
import uuid
from PIL import Image
import time
import traceback
import sys
import time
import requests

# celery
from WSUDOR_Manager import celery

# eulfedora
import eulfedora

import WSUDOR_Manager

import localConfig

# handles
from WSUDOR_Manager.solrHandles import solr_handle
from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager import redisHandles

# import WSUDOR_ContentTypes
import WSUDOR_ContentTypes

# import manifest factory instance
from inc.manifest_factory import iiif_manifest_factory_instance

# import API functions
import WSUDOR_API


class WSUDOR_Collection(WSUDOR_ContentTypes.WSUDOR_GenObject):

	# static values for class
	label = "Collection"
	description = "Content Type for Collection Objects."
	Fedora_ContentType = "CM:Collection"
	version = 1

	def __init__(self,object_type=False,content_type=False,payload=False,orig_payload=False):
		
		# run __init__ from parent class
		WSUDOR_ContentTypes.WSUDOR_GenObject.__init__(self,object_type, content_type, payload, orig_payload)
		
		# Add WSUDOR_Image struct_requirements to WSUDOR_Object instance struct_requirements
		self.struct_requirements['WSUDOR_Collection'] = {
			"datastreams":[],
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
			report_failure(("isRepresentedBy_check","%s is not in %s" % (self.objMeta['isRepresentedBy'], ds_ids)))

		# check that content_type is a valid ContentType				
		if self.__class__ not in WSUDOR_ContentTypes.WSUDOR_GenObject.__subclasses__():
			report_failure(("Valid ContentType","WSUDOR_Object instance's ContentType: %s, not found in acceptable ContentTypes: %s " % (self.content_type, WSUDOR_ContentTypes.WSUDOR_GenObject.__subclasses__())))
				
		# finally, return verdict
		return results_dict


	# ingest image type
	def ingestBag(self,indexObject=True):
		if self.object_type != "bag":
			raise Exception("WSUDOR_Object instance is not 'bag' type, aborting.")		

		# ingest collection object
		try:
			self.ohandle = fedora_handle.get_object(self.objMeta['id'],create=True)
			self.ohandle.save()

			# set base properties of object
			self.ohandle.label = self.objMeta['label']

			# write POLICY datastream (NOTE: 'E' management type required, not 'R')
			print "Using policy:",self.objMeta['policy']
			policy_suffix = self.objMeta['policy'].split("info:fedora/")[1]
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
			self.ohandle.add_relationship("http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isRepresentedBy",self.objMeta['isRepresentedBy'])
			content_type_string = "info:fedora/CM:"+self.objMeta['content_type'].split("_")[1]
			self.ohandle.add_relationship("info:fedora/fedora-system:def/relations-external#hasContentModel",content_type_string)

			# write MODS datastream
			objMeta_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "MODS", "MODS descriptive metadata", mimetype="text/xml", control_group='M')
			objMeta_handle.label = "MODS descriptive metadata"
			file_path = self.Bag.path + "/data/MODS.xml"
			objMeta_handle.content = open(file_path)
			objMeta_handle.save()			

			# create derivatives and write datastreams
			for ds in self.objMeta['datastreams']:

				if "skip_processing" not in ds:
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
					if im.mode != "RGB":
						im = im.convert("RGB")
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
					im.thumbnail((max_width, max_height), Image.ANTIALIAS)
					if im.mode != "RGB":
						im = im.convert("RGB")
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
					im.thumbnail((max_width, max_height), Image.ANTIALIAS)
					if im.mode != "RGB":
						im = im.convert("RGB")
					im.save(temp_filename,'JPEG')
					preview_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "%s_PREVIEW" % (ds['ds_id']), "%s_PREVIEW" % (ds['label']), mimetype="image/jpeg", control_group='M')
					preview_handle.label = "%s_PREVIEW" % (ds['label'])
					preview_handle.content = open(temp_filename)
					preview_handle.save()
					os.system('rm %s' % (temp_filename))

					# make jp2
					temp_filename = "/tmp/Ouroboros/"+str(uuid.uuid4())+".jp2"
					os.system("convert %s %s[256x256]" % (file_path, temp_filename))
					jp2_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "%s_JP2" % (ds['ds_id']), "%s_JP2" % (ds['label']), mimetype="image/jp2", control_group='M')
					jp2_handle.label = "%s_JP2" % (ds['label'])
					try:
						jp2_handle.content = open(temp_filename)
					except:
						# sometimes jp2 creation results in two files, look for first one in this instance
						temp_filename = temp_filename.split(".")[0]
						temp_filename = temp_filename + "-0.jp2"
						jp2_handle.content = open(temp_filename)
					jp2_handle.save()
					os.system('rm %s' % (temp_filename))

					# add to RELS-INT
					fedora_handle.api.addRelationship(self.ohandle,'info:fedora/%s/%s' % (self.ohandle.pid, ds['ds_id']),'info:fedora/fedora-system:def/relations-internal#isPartOf','info:fedora/%s' % (self.ohandle.pid))
					fedora_handle.api.addRelationship(self.ohandle,'info:fedora/%s/%s_THUMBNAIL' % (self.ohandle.pid, ds['ds_id']),'info:fedora/fedora-system:def/relations-internal#isThumbnailOf','info:fedora/%s/%s' % (self.ohandle.pid, ds['ds_id']))
					fedora_handle.api.addRelationship(self.ohandle,'info:fedora/%s/%s_JP2' % (self.ohandle.pid, ds['ds_id']),'info:fedora/fedora-system:def/relations-internal#isJP2Of','info:fedora/%s/%s' % (self.ohandle.pid, ds['ds_id']))
					fedora_handle.api.addRelationship(self.ohandle,'info:fedora/%s/%s_PREVIEW' % (self.ohandle.pid, ds['ds_id']),'info:fedora/fedora-system:def/relations-internal#isPreviewOf','info:fedora/%s/%s' % (self.ohandle.pid, ds['ds_id']))
					fedora_handle.api.addRelationship(self.ohandle,'info:fedora/%s/%s_ACCESS' % (self.ohandle.pid, ds['ds_id']),'info:fedora/fedora-system:def/relations-internal#isAccessOf','info:fedora/%s/%s' % (self.ohandle.pid, ds['ds_id']))


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
			for gen_type in ['THUMBNAIL','PREVIEW']:
				thumb_rep_handle = eulfedora.models.DatastreamObject(self.ohandle,gen_type, gen_type, mimetype="image/jpeg", control_group="M")
				thumb_rep_handle.ds_location = "http://localhost/fedora/objects/%s/datastreams/%s_%s/content" % (self.ohandle.pid, self.objMeta['isRepresentedBy'], gen_type)
				thumb_rep_handle.label = gen_type
				thumb_rep_handle.save()


			# save and commit object before finishIngest()
			final_save = self.ohandle.save()


			# finish generic ingest
			return self.finishIngest()


		# exception handling
		except Exception,e:
			print traceback.format_exc()
			print "Collection Ingest Error:",e
			return False


	# ingest image type
	def genIIIFManifest(self):

		stime = time.time()

		# create root mani obj
		try:
			manifest = iiif_manifest_factory_instance.manifest( label=self.SolrDoc.asDictionary()['mods_title_ms'][0] )
		except:
			manifest = iiif_manifest_factory_instance.manifest( label="Unknown Title" )
		manifest.viewingDirection = "left-to-right"

		# build metadata
		'''
		Order of preferred fields is the order they will show on the viewer
		NOTE: solr items are stored here as strings so they won't evaluate
		'''
		preferred_fields = [
			("Title", "self.SolrDoc.asDictionary()['mods_title_ms'][0]"),
			("Description", "self.SolrDoc.asDictionary()['mods_abstract_ms'][0]"),
			("Year", "self.SolrDoc.asDictionary()['mods_key_date_year'][0]"),
			("Item URL", "\"<a href='%s'>%s</a>\" % (self.SolrDoc.asDictionary()['mods_location_url_ms'][0],self.SolrDoc.asDictionary()['mods_location_url_ms'][0])"),
			("Original", "self.SolrDoc.asDictionary()['mods_otherFormat_note_ms'][0]")
		]
		for field_set in preferred_fields:
			try:
				manifest.set_metadata({ field_set[0]:eval(field_set[1]) })
			except:
				print "Could Not Set Metadata Field, Skipping",field_set[0]
	
		# start anonymous sequence
		seq = manifest.sequence(label="collection thumbs")

		# get component parts		
		'''
		For collection object, this will be all children objects.
		Interesting hack here: use API functions without traversing twisted HTTP cycle
		'''
		obj_list = json.loads( WSUDOR_API.functions.availableFunctions.hasMemberOfCollection({'PID':[self.pid]}) )		

		# iterate through component parts
		for obj in obj_list['results']:
			
			print "adding",obj['memberTitle']

			# generate obj|ds self.pid as defined in loris TemplateHTTP extension
			fedora_http_ident = "fedora:%s|%s" % (obj['object'], obj['isRepBy']+"_JP2")
			# fedora_http_ident = "%s|%s" % (obj['object'], obj['isRepBy']+"_JP2") #loris_dev

			# Create a canvas with uri slug 
			cvs = seq.canvas(ident=fedora_http_ident, label=obj['memberTitle'])	

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

		# report time
		etime = time.time()
		ttime = etime - stime
		print "total time",ttime

		# redisHandles.r_iiif.set(self.pid,manifest.toString())
		return manifest.toString()


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
	def _createVirtCollection(self):

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

		virtual_book_handle = fedora_handle.get_object(type=WSUDOR_ContentTypes.WSUDOR_Readux_VirtualCollection)
		virtual_book_handle.create(self)


	def createReaduxVirtualObjects(self):

		self._createVirtCollection()
	


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
		

		
