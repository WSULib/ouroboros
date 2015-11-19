from localConfig import *

import sys
import requests
import json
from eulfedora.server import Repository

# init FC connection
repo = Repository(FEDORA_ROOT,FEDORA_USER,FEDORA_PASSWORD,FEDORA_PIDSPACE)

def augmentCore(PID):
	
	print "Checking",PID

	'''
	Can improve with WSUDOR_ContentTypes - in fact, farm out functions to them
	'''
	
	# for all 'wayne' prefixes
	if PID.startswith("wayne:"):
		# get content type
		obj_ohandle = repo.get_object(PID)			
		obj_risearch = obj_ohandle.risearch
		obj_spo = obj_risearch.spo_search("info:fedora/{PID}".format(PID=PID), "info:fedora/fedora-system:def/relations-external#hasContentModel")
		obj_objects = obj_spo.objects()
		for obj in obj_objects:
			# ebooks
			if str(obj) == "info:fedora/CM:WSUebook":			
				ebookText(PID)

	#######################################################
	# consider adding more advanced indexing here, e.g. 
	#######################################################

	else:
		print "Does not have 'wayne' prefix, skipping augmentCore()..."		

def ebookText(PID):		
			
	# derive fullbook PID	
	fullbook_ohandle = repo.get_object(PID)

	# get ds content
	ds_handle = fullbook_ohandle.getDatastreamObject("HTML_FULL")
	ds_content = ds_handle.content
	
	# assume v1 book, attempt ds_content again
	if ds_content == None:		

		# derive fullbook PID	
		fullbook_ohandle = repo.get_object(PID.split(":")[1]+":fullbook")
		ds_handle = fullbook_ohandle.getDatastreamObject("HTML_FULL")
		ds_content = ds_handle.content

	# use Solr's Tika Extract to strip down to text
	baseurl = "http://localhost/solr4/fedobjs/update/extract?&extractOnly=true"
	files = {'file': ds_content}		
	r = requests.post(baseurl, files=files)
	ds_stripped_content = r.text	
		

	# atomically update in solr
	baseurl = "http://localhost/solr4/fedobjs/update?commit=true"
	headers = {'Content-Type': 'application/json'}
	data = [{
		"id":PID,
		"int_fullText":{"set":ds_stripped_content},			
	}]		 
	data_json = json.dumps(data)
	r = requests.post(baseurl, data=data_json, headers=headers)
	




