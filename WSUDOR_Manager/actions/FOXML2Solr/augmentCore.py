# ancillary utility to FOXML2Solr that, for a given list of PIDs, checks their CM type and/or datastream mime/types and indexs documents in /search core
from localConfig import *

import sys
import requests
import json
from eulfedora.server import Repository

# init FC connection
repo = Repository(FEDORA_ROOT,FEDORA_USER,FEDORA_PASSWORD,FEDORA_PIDSPACE)

def augmentCore(toUpdate):
	count = 1
	tcount = len(toUpdate)

	for PID in toUpdate:
		print "Checking",PID,count,"/",tcount
		count = count + 1
		
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
			print "Does not have 'wayne' prefix, skipping..."		

def ebookText(PID):		
			
	# derive fullbook PID
	PID_suffix = PID.split(":")[1] 
	fullbook_PID = PID_suffix+":fullbook"
	fullbook_ohandle = repo.get_object(fullbook_PID)

	# get ds content
	ds_handle = fullbook_ohandle.getDatastreamObject("HTML_FULL")
	ds_content = ds_handle.content		

	# use Solr's Tika Extract to strip down to text
	baseurl = "http://silo.lib.wayne.edu/solr4/fedobjs/update/extract?&extractOnly=true"
	files = {'file': ds_content}		
	r = requests.post(baseurl, files=files)		
	ds_stripped_content = r.text

	# atomically update in solr
	baseurl = "http://silo.lib.wayne.edu/solr4/fedobjs/update?commit=true"
	headers = {'Content-Type': 'application/json'}
	data = [{
		"id":"wayne:{PID_suffix}".format(PID_suffix=PID_suffix),
		"int_fullText":{"set":ds_stripped_content},			
	}]		 
	data_json = json.dumps(data)
	r = requests.post(baseurl, data=data_json, headers=headers)
	




