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

	# init worker with built-in timers
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
		# Returns streaming socket iterator with PIDs
		'''
		
		risearch_query = "select $object from <#ri> where $object <info:fedora/fedora-system:def/model#hasModel> <info:fedora/fedora-system:FedoraObject-3.0> and $object <fedora-view:lastModifiedDate> $modified and $modified <mulgara:after> '{lastFedoraIndexDate}'^^<xml-schema:dateTime> in <#xsd>".format(lastFedoraIndexDate=lastFedoraIndexDate)

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
		modified_objects.next() # bump past headers
		return modified_objects


	def indexFOXMLinSolr(self, PID, outputs):

		print "Indexing PID:",PID		

		# instantiate handle
		obj_handle = WSUDOR_ContentTypes.WSUDOR_Object(object_type="WSUDOR",payload=PID)

		# build obj_handle.SolrDoc.doc 

		# built-ins from ohandle
		obj_handle.SolrDoc.doc.obj_label = obj_handle.ohandle.label
		obj_handle.SolrDoc.doc.obj_createdDate = obj_handle.ohandle.created.isoformat()+"Z"
		obj_handle.SolrDoc.doc.obj_modifiedDate = obj_handle.ohandle.modified.isoformat()+"Z"

		# MODS
		try:
			for each in obj_handle.MODS_Solr_flat['fields']['field']:
				try:
					if type(each['@name']) == unicode:
						setattr(obj_handle.SolrDoc.doc,each['@name'],each['#text'])
				except:
					print "Could not add",each
		except:
			print "Could not find datastream MODS"

		# DC
		try:
			for each in obj_handle.DC_Solr_flat['fields']['field']:
				try:
					if type(each['@name']) == unicode:
						setattr(obj_handle.SolrDoc.doc,each['@name'],each['#text'])
				except:
					print "Could not add",each
		except:
			print "Could not find datastream DC"

		# RELS-EXT
		try:
			for each in obj_handle.RELS_EXT_Solr_flat['fields']['field']:
				try:
					if type(each['@name']) == unicode:
						setattr(obj_handle.SolrDoc.doc,each['@name'],each['#text'])
				except:
					print "Could not add",each
		except:
			print "Could not find datastream RELS-EXT"

		# RELS-INT
		try:
			for each in obj_handle.RELS_INT_Solr_flat['fields']['field']:
				try:
					if type(each['@name']) == unicode:
						setattr(obj_handle.SolrDoc.doc,each['@name'],each['#text'])
				except:
					print "Could not add",each
		except:
			print "Could not find datastream RELS-INT"

		# update object, no commit yet
		obj_handle.SolrDoc.update()


	def commitSolrChanges(self):		
		print "*** Committing Changes ***"
		result = solr_manage_handle.commit()
		print result
		return result

	
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
		doc_handle.doc.last_modified = "NOW"
		result = doc_handle.update()
		return result.raw_content

	
	def removeFOXMLinSolr(self, PID):		

		doc_handle = models.SolrDoc(PID)
		result = doc_handle.delete()		
		return result.raw_content




@celery.task()
def solrIndexer(fedEvent, PID):	

	# simple function to clean PID from /risearch
	def cleanPID(PID):
		return PID.split("/")[1].rstrip()

	
	#Set output filenames
	now = datetime.datetime.now().isoformat()
	outputs = {}
	outputs['downloadExcepts'] = './reports/'+now+'_downloadExcepts.csv'
	outputs['transformExcepts'] = './reports/'+now+'_transformExcepts.csv'
	outputs['indexExcepts'] = './reports/'+now+'_indexExcepts.csv'

	# init worker
	worker = SolrIndexerWorker()

	# determine action based on fedEvent
	# timestamp based
	if fedEvent == "timestampIndex":

		print "Indexing all Fedora items that have been modified since last solrIndexer run"
		
		# generate list of PIDs to update
		toUpdate = worker.getToUpdate(worker.lastFedoraIndexDate)

		# begin iterating through
		for PID in toUpdate.readlines():
			PID = cleanPID(PID)
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
		
		# generate list of PIDs to update
		toUpdate = worker.getToUpdate("1969-12-31T12:59:59.265Z")		
		
		# begin iterating through
		for PID in toUpdate.readlines():
			PID = cleanPID(PID)
			# index PIDs in Solr
			worker.indexFOXMLinSolr(PID, outputs)
			# augment documents - from augmentCore.py
			augmentCore(PID)
		# update timestamp in Solr		
		worker.updateLastFedoraIndexDate()
		# commit changes
		worker.commitSolrChanges()
		# replicate changes to /search core
		worker.replicateToSearch()
		
		print "Total seconds elapsed",worker.totalTime	
		

	# Index single item per fedEvent
	if fedEvent == "modifyDatastreamByValue" or fedEvent == "ingest" or fedEvent == "modifyObject":

		print "Updating / Indexing",PID
		# index PIDs in Solr
		worker.indexFOXMLinSolr(PID,outputs)
		# augment documents - from augmentCore.py
		augmentCore(PID)
		# update timestamp in Solr		
		worker.updateLastFedoraIndexDate()
		# commit changes
		worker.commitSolrChanges()
		# replicate changes to /search core
		worker.replicateToSearch()		
		return True

	# Remove Object from Solr Index on Purge
	if fedEvent == "purgeObject":
		print "Removing the following from Solr Index",PID		
		worker.removeFOXMLinSolr(PID)
		# commit changes
		worker.commitSolrChanges()
		# replicate changes to /search core
		worker.replicateToSearch()
		return True


if __name__ == '__main__':
	# running as OS script indexes all recently modified
	solrIndexer("timestampIndex","")
























