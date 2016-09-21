from localConfig import *

import sys
import requests
import json
from eulfedora.server import Repository

# WSUDOR
import WSUDOR_ContentTypes
from WSUDOR_Manager.fedoraHandles import fedora_handle


'''
Improvements:
	- farm out to WSUDOR_ContentTypes
'''

def augmentCore(PID):
	
	print "Checking",PID	
	
	# for all 'wayne' prefixes
	if PID.startswith("wayne:"):
		# get content type
		obj_ohandle = fedora_handle.get_object(PID)			
		obj_risearch = obj_ohandle.risearch
		obj_spo = obj_risearch.spo_search("info:fedora/%s" % (PID), "info:fedora/fedora-system:def/relations-external#hasContentModel")
		obj_objects = obj_spo.objects()
		for obj in obj_objects:
			
			# ebooks
			if str(obj) == "info:fedora/CM:WSUebook":	
				print "Firing ebook augment"		
				ebookText(PID)

			# hierarchicalfiles
			if str(obj) == "info:fedora/CM:HierarchicalFiles":			
				print "Firing hierarchical augment"
				hierarchicalDocuments(PID)

	#######################################################
	# consider adding more advanced indexing here, e.g. 
	#######################################################

	else:
		print "Does not have 'wayne' prefix, skipping augmentCore()..."		

def ebookText(PID):		

	# open handle
	obj_handle = WSUDOR_ContentTypes.WSUDOR_Object(PID)	

	# get ds content
	ds_handle = obj_handle.ohandle.getDatastreamObject("HTML_FULL")
	ds_content = ds_handle.content
	
	# assume v1 book, attempt ds_content again
	if ds_content == None:		

		# derive fullbook PID	
		obj_handle.ohandle = fedora_handle.get_object(PID.split(":")[1]+":fullbook")
		ds_handle = obj_handle.ohandle.getDatastreamObject("HTML_FULL")
		ds_content = ds_handle.content

	# use Solr's Tika Extract to strip down to text
	baseurl = "http://localhost/solr4/fedobjs/update/extract?&extractOnly=true"
	files = {'file': ds_content}		
	r = requests.post(baseurl, files=files)
	ds_stripped_content = r.text	

	# atomically update in solr
	baseurl = "http://localhost/solr4/fedobjs/update?commit=false"
	headers = {'Content-Type': 'application/json'}
	data = [{
		"id":PID,
		"int_fullText":{"set":ds_stripped_content},			
	}]		 
	data_json = json.dumps(data)
	r = requests.post(baseurl, data=data_json, headers=headers)

	# finally, index each page to /bookreader core
	print "running page index"
	obj_handle.indexPageText()
	

def hierarchicalDocuments(PID):
	print "augmenting object with fulltext"

	obj_handle = WSUDOR_ContentTypes.WSUDOR_Object(PID)

	# clean out int_fullText field for object (because 'adding', not 'setting' below)
	print "cleaning out int_fullText field"
	baseurl = "http://localhost/solr4/fedobjs/update?commit=false"
	headers = {'Content-Type': 'application/json'}
	data = [{
		"id":PID,
		"int_fullText":{"remove":"*"},			
	}]		 
	data_json = json.dumps(data)
	r = requests.post(baseurl, data=data_json, headers=headers)
	print r.text


	# get all PDF's
	pdf_ds_list = [ 
			ds for ds in obj_handle.ohandle.ds_list 
			if obj_handle.ohandle.ds_list[ds].mimeType == "application/pdf" 
			and obj_handle.ohandle.getDatastreamObject(ds).control_group != 'R' 
		]

	for pdf in pdf_ds_list:
		
		# get handle
		pdf_ds_handle = obj_handle.ohandle.getDatastreamObject(pdf)

		# use Solr's Tika Extract to strip down to text
		print "extracting full-text from PDF"
		baseurl = "http://localhost/solr4/fedobjs/update/extract?&extractOnly=true"
		files = {'file': pdf_ds_handle.content}		
		r = requests.post(baseurl, files=files)
		ds_stripped_content = r.text	

		# atomically update in solr
		print "updating in Solr"
		baseurl = "http://localhost/solr4/fedobjs/update?commit=false"
		headers = {'Content-Type': 'application/json'}
		data = [{
			"id":PID,
			"int_fullText":{"add":ds_stripped_content},			
		}]		 
		data_json = json.dumps(data)
		r = requests.post(baseurl, data=data_json, headers=headers)




