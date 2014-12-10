#Utility to link Fedora Commons objects and Solr, with augmentation in /search core

import os
import sys
import xml.etree.ElementTree as ET
import urllib, urllib2
import requests
from string import Template
import time
import datetime
from lxml import etree
from flask import Blueprint, render_template, make_response, abort, request
import json

# celery
from cl.cl import celery
from celery import Task

# WSUDOR
from localConfig import *
from WSUDOR_Manager.solrHandles import solr_handle, solr_manage_handle
from WSUDOR_Manager.fedoraHandles import fedora_handle
import WSUDOR_ContentTypes
from WSUDOR_Manager import models
import WSUDOR_Manager.actions as actions

# augmentCore 
from augmentCore import augmentCore

# define blueprint
solrIndexer_blue = Blueprint('solrIndexer', __name__, template_folder='templates')


'''
ToDo
- create function to return clean PIDs (.rstrip())
- finish up the others - FullIndex, single PID
- REALWORK: redo indexFOXMLinSolr()
	- use SolrLink object? or SolrDoc?
	- generate object.doc dictionary, then .update()
'''


@solrIndexer_blue.route("/updateSolr/<update_type>", methods=['POST', 'GET'])
def updateSolr(update_type):			

	if update_type == "fullIndex":				
		index_handle = solrIndexer.delay('fullIndex','')

	if update_type == "timestamp":
		print "Updating by timestamp"	
		index_handle = solrIndexer.delay('timestampIndex','')
		
	# return logic
	if "APIcall" in request.values and request.values['APIcall'] == "True":

		# prepare package
		return_dict = {
			"solrIndexer":{
				"update_type":update_type,
				"timestamp":datetime.datetime.now().isoformat(),
				"job_celery_ID":index_handle.id
			}
		}

		# return JSON
		print return_dict
		json_string = json.dumps(return_dict)
		resp = make_response(json_string)
		resp.headers['Content-Type'] = 'application/json'
		return resp		
	
	else:
		return render_template("updateSolr.html",update_type=update_type)



class SolrIndexerWorker(object):

	def __init__(self):
		self.startTime = int(time.time())

	@property
	def endTime(self):
		return int(time.time())

	@property
	def totalTime(self):
		return self.endTime - self.startTime

	
	@property
	def lastFedoraIndexDate(self):
		
		'''
		Function to retrieve last Fedora Update
		'''

		doc_handle = models.SolrDoc("LastFedoraIndex")
		if doc_handle.exists == True:
			return doc_handle.doc.last_modified
		else:
			return False


	
	def getToUpdate(self, lastFedoraIndexDate):

		'''
		# Get Objects/Datastreams modified on or after this date
		# FYI, this line will limit to only objects: and $object<info:fedora/fedora-system:def/relations-external#isMemberOfCollection> <info:fedora/wayne:collectionBMC>
		# Returns streaming socket iterator with PIDs
		'''
		
		risearch_query = "select $object from <#ri> where $object <info:fedora/fedora-system:def/model#hasModel> <info:fedora/fedora-system:FedoraObject-3.0> and $object <fedora-view:lastModifiedDate> $modified and $modified <mulgara:after> '{lastFedoraIndexDate}'^^<xml-schema:dateTime> in <#xsd>".format(lastFedoraIndexDate=lastFedoraIndexDate)

		print risearch_query

		risearch_params = urllib.urlencode({
			'type': 'tuples', 
			'lang': 'itql', 
			'format': 'CSV',
			'limit':'',
			'dt': 'on',
			'stream':'on',
			'query': risearch_query
			})
		risearch_host = "http://{FEDORA_USER}:{FEDORA_PASSWORD}@silo.lib.wayne.edu/fedora/risearch?".format(FEDORA_USER=FEDORA_USER,FEDORA_PASSWORD=FEDORA_PASSWORD)

		modified_objects = urllib.urlopen(risearch_host,risearch_params)
		# bump past headers
		modified_objects.next()
		return modified_objects

			
	def indexFOXMLinSolr(self, PID, outputs):

		print "Indexing PID:",PID
		
		#get object FOXML and parse as XML
		try:
			response = urllib.urlopen("http://{FEDORA_USER}:{FEDORA_PASSWORD}@silo.lib.wayne.edu/fedora/objects/{PID}/objectXML".format(PID=PID,FEDORA_USER=FEDORA_USER,FEDORA_PASSWORD=FEDORA_PASSWORD))
			FOXML = response.read()
			XMLroot = etree.fromstring(FOXML)		
		except:
			print "Could not DOWNLOAD FOXML for",PID
			fhand_exceptions = open(outputs['downloadExcepts'],'a')
			fhand_exceptions.write(str(PID)+"\n")
			fhand_exceptions.close()

		#get XSL doc, parse as XSL, transform FOXML as Solr add-doc
		try:			
			XSLhand = open('inc/xsl/FOXML_to_Solr.xsl','r')		
			xslt_tree = etree.parse(XSLhand)
	  		transform = etree.XSLT(xslt_tree)
			SolrXML = transform(XMLroot)
		except:
			print "Could not TRANSFORM FOXML for",PID
			fhand_exceptions = open(outputs['transformExcepts'],'a')
			fhand_exceptions.write(str(PID)+"\n")
			fhand_exceptions.close()

		#index Solr-ready XML (SolrXML)		 
		try:
			# print SolrXML
			updateURL = "http://silo.lib.wayne.edu/solr4/fedobjs/update/"								
			headers = {'Content-Type': 'application/xml'}
			r = requests.post(updateURL, data=str(SolrXML), headers=headers)
			print r.text
		except:
			print "Could not INDEX FOXML for",PID
			fhand_exceptions = open(outputs['indexExcepts'],'a')
			fhand_exceptions.write(str(PID)+"\n")
			fhand_exceptions.close()	
	
	
	def commitSolrChanges(self):		

		return solr_manage_handle.commit()

	
	def replicateToSearch(self):

		'''
		Consider adding to MySolr module....
		'''
		
		# replicate to "search core"
		print "*** Replicating Changes ***"
		baseurl = 'http://silo.lib.wayne.edu/solr4/search/replication?command=fetchindex' 
		data = {'commit':'true'}
		r = requests.post(baseurl,data=data)
		print r.text	

	
	def updateLastFedoraIndexDate(self):		

		doc_handle = models.SolrDoc("LastFedoraIndex")
		# doc_handle.doc.last_modified = "NOW"
		doc_handle.doc.last_modified = "2014-12-08T15:29:22.417Z"
		result = doc_handle.update()
		return result.raw_content

	
	def removeFOXMLinSolr(self, PID):		

		doc_handle = models.SolrDoc(PID)
		result = doc_handle.delete()		
		return result.raw_content




@celery.task()
def solrIndexer(fedEvent, PID):	

	# determine action based on fedEvent

	#Set output filenames
	now = datetime.datetime.now().isoformat()
	outputs = {}
	outputs['downloadExcepts'] = './reports/'+now+'_downloadExcepts.csv'
	outputs['transformExcepts'] = './reports/'+now+'_transformExcepts.csv'
	outputs['indexExcepts'] = './reports/'+now+'_indexExcepts.csv'


	# timestamp based
	if fedEvent == "timestampIndex":

		print "Indexing all Fedora items that have been modified since last solrIndexer run"
		
		# init worker
		worker = SolrIndexerWorker()
		
		# generate list of PIDs to update
		# toUpdate = worker.getToUpdate(worker.lastFedoraIndexDate)
		toUpdate = worker.getToUpdate('2014-12-08T01:12:05.589Z')

		# begin iterating through
		for PID in toUpdate.readlines():
			PID = PID.split("/")[1].rstrip()
			# index PIDs in Solr
			worker.indexFOXMLinSolr(PID,outputs)
			# augment documents - from augmentCore.py
			augmentCore(PID)
		# close handle
		toUpdate.close()
		# update timestamp in Solr		
		worker.updateLastFedoraIndexDate()
		# commit changes
		worker.commitSolrChanges()
		# replicate changes to /search core
		worker.replicateToSearch()			

		print "Total seconds elapsed",worker.totalTime	

		


	# fullindex
	if fedEvent == "fullIndex":
		print "Indexing ALL Fedora items."
		
		#Globals
		toUpdate = []				

		#start timer
		startTime = int(time.time())		

		LastFedoraIndexDate = "1969-12-31T12:59:59.265Z"
		
		# generate list of PIDs to update
		result = getToUpdate(LastFedoraIndexDate)		
		
		# index PIDs in Solr
		indexFOXMLinSolr(toUpdate)
		# augment documents - from augmentCore.py
		augmentCore(toUpdate)	
		# update timestamp in Solr		
		updateLastFedoraIndexDate()
		# commit changes
		commitSolrChanges()
		# replicate changes to /search core
		replicateToSearch()			

		#end timer
		endTime = int(time.time())
		totalTime = endTime - startTime
		print "Total seconds elapsed",totalTime	
		

	# Index single item per fedEvent
	if fedEvent == "modifyDatastreamByValue" or fedEvent == "ingest" or fedEvent == "modifyObject":

		print "Updating / Indexing",PID
		toUpdate = [PID]
		# index PIDs in Solr
		indexFOXMLinSolr(toUpdate)
		# augment documents - from augmentCore.py
		augmentCore(toUpdate)
		# update timestamp in Solr		
		updateLastFedoraIndexDate()
		# commit changes
		commitSolrChanges()
		# replicate changes to /search core
		replicateToSearch()		
		return

	# Remove Object from Solr Index on Purge
	if fedEvent == "purgeObject":
		print "Removing the following from Solr Index",PID		
		removeFOXMLinSolr(PID)
		# commit changes
		commitSolrChanges()
		# replicate changes to /search core
		replicateToSearch()
		return





if __name__ == '__main__':
	# running as OS script indexes all recently modified
    solrIndexer("timestampIndex","")
























