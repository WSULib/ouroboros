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
from WSUDOR_Manager import models, jobs, helpers
import WSUDOR_Manager.actions as actions

# augmentCore 
from augmentCore import augmentCore

import localConfig

# define blueprint
solrIndexer_blue = Blueprint('solrIndexer', __name__, template_folder='templates')


@solrIndexer_blue.route("/updateSolr/<update_type>", methods=['POST', 'GET'])
def updateSolr(update_type):			


	# real or emulated solr events
	if update_type == "fullIndex":				
		index_handle = solrIndexer.delay('fullIndex','')

	if update_type == "timestamp":
		print "Updating by timestamp"	
		index_handle = solrIndexer.delay('timestampIndex','')

	if update_type == "userObjects":
		print "Updating by userObjects"	
		PIDs = jobs.getSelPIDs()
		for PID in PIDs:
			index_handle = solrIndexer.delay('modifyObject', PID)	

	# purge and reindex staging solr core from fedora (SLOW)
	if update_type == "purgeAndFullIndex":
		print "Purging solr core and reindexing all objects"
		# delete all from /fedobjs core
		if 'fedobjs' in solr_manage_handle.base_url:
			solr_manage_handle.delete_by_query('*:*',commit=False)
		# run full index	
		index_handle = solrIndexer.delay('fullIndex','')

	# purge production core, replicate from staging (FAST)
	if update_type == "replicateStagingToProduction":
		index_handle = solrIndexer.delay('replicateStagingToProduction','')


	# return logic
	if "APIcall" in request.values and request.values['APIcall'] == "True":

		# prepare package
		return_dict = {
			"solrIndexer":{
				"update_type":update_type,
				"timestamp":datetime.datetime.now().isoformat(),
				"job_ID":index_handle.id
			}
		}
		# return JSON
		print return_dict
		json_string = json.dumps(return_dict)
		resp = make_response(json_string)
		resp.headers['Content-Type'] = 'application/json'
		return resp		
	
	else:
		return render_template("updateSolr.html",update_type=update_type,APP_HOST=localConfig.APP_HOST)



class SolrIndexerWorker(object):

	# init worker with built-in timers
	def __init__(self, printOnly):
		self.startTime = int(time.time())
		self.printOnly = printOnly

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
		risearch_host = "http://{FEDORA_USER}:{FEDORA_PASSWORD}@localhost/fedora/risearch?".format(FEDORA_USER=FEDORA_USER,FEDORA_PASSWORD=FEDORA_PASSWORD)

		modified_objects = urllib.urlopen(risearch_host,risearch_params)
		modified_objects.next() # bump past headers
		return modified_objects


	def indexFOXMLinSolr(self, PID, outputs):

		print "Indexing PID:",PID		

		# instantiate handle
		obj_handle = WSUDOR_ContentTypes.WSUDOR_Object(PID)	

		# skip if no valid WSUDOR_ContentType object		
		if obj_handle == False:
			return False

		# purge previous Solr doc content
		obj_handle.SolrDoc.doc = helpers.BlankObject()
		obj_handle.SolrDoc.doc.id = obj_handle.pid

		# built-ins from ohandle
		obj_handle.SolrDoc.doc.obj_label = obj_handle.ohandle.label
		obj_handle.SolrDoc.doc.obj_createdDate = obj_handle.ohandle.created.isoformat()+"Z"
		obj_handle.SolrDoc.doc.obj_modifiedDate = obj_handle.ohandle.modified.isoformat()+"Z"

		# MODS
		try:
			for each in obj_handle.MODS_Solr_flat['fields']['field']:
				try:
					if type(each['@name']) == unicode:				
						fname = each['@name']
						fvalue = each['#text'].rstrip()
						if hasattr(obj_handle.SolrDoc.doc, fname) == False:
							# create empty list
							setattr(obj_handle.SolrDoc.doc, fname, [])
						# append to list
						getattr(obj_handle.SolrDoc.doc, fname).append(fvalue)
				except:
					print "Could not add",each
		except:
			print "Could not find or index datastream MODS"

		# DC
		try:
			for each in obj_handle.DC_Solr_flat['fields']['field']:
				try:
					if type(each['@name']) == unicode:				
						fname = each['@name']
						fvalue = each['#text'].rstrip()
						if hasattr(obj_handle.SolrDoc.doc, fname) == False:
							# create empty list
							setattr(obj_handle.SolrDoc.doc, fname, [])
						# append to list
						getattr(obj_handle.SolrDoc.doc, fname).append(fvalue)
				except:
					print "Could not add",each
		except:
			print "Could not find or index datastream DC"

		# RELS-EXT
		try:
			for each in obj_handle.RELS_EXT_Solr_flat['fields']['field']:
				try:
					if type(each['@name']) == unicode:				
						fname = each['@name']
						fvalue = each['#text'].rstrip()
						if hasattr(obj_handle.SolrDoc.doc, fname) == False:
							# create empty list
							setattr(obj_handle.SolrDoc.doc, fname, [])
						# append to list
						getattr(obj_handle.SolrDoc.doc, fname).append(fvalue)
				except:
					print "Could not add",each
		except:
			print "Could not find or index datastream RELS-EXT"

		# Add object and datastream sizes
		try:
			setattr(obj_handle.SolrDoc.doc, "obj_size_i", obj_handle.objSizeDict['total_size'][0] )
			setattr(obj_handle.SolrDoc.doc, "obj_size_human", obj_handle.objSizeDict['total_size'][1] )
		except:
			print "Could not determine object size, skipping"


		#######################################################################################
		# Here, we have the opportunity to do some cleanup, addition, and finagling of fields.
		#######################################################################################
		
		if self.printOnly == True:
			# print and return dicitonary, but do NOT update, commit, or replicate
			print "DEBUG: printing only"
			print obj_handle.SolrDoc.doc.__dict__
			return obj_handle.SolrDoc.doc.__dict__

		else:
			# update object, no commit yet
			obj_handle.SolrDoc.update()
			return True


	def commitSolrChanges(self):		
		print "*** Committing Changes ***"
		result = solr_manage_handle.commit()
		print result
		return result

	
	def replicateToSearch(self):

		'''
		Currently skipping this - moving to manual replication from /fedobjs --> /search core
		'''

		pass
		
		# # replicate to "search core"
		# print "*** Replicating Changes ***"
		# baseurl = 'http://localhost/solr4/search/replication?command=fetchindex' 
		# data = {'commit':'true'}
		# r = requests.post(baseurl,data=data)
		# print r.text	

	
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
def solrIndexer(fedEvent, PID, printOnly=SOLR_INDEXER_WRITE_DEFAULT):

	print "solrIndexer running"

	# simple function to clean PID from /risearch
	def cleanPID(PID):
		return PID.split("/")[1].rstrip()

	#Set output filenames
	now = datetime.datetime.now().isoformat()
	outputs = {}
	outputs['downloadExcepts'] = './reports/'+now+'_downloadExcepts.csv'
	outputs['transformExcepts'] = './reports/'+now+'_transformExcepts.csv'
	outputs['indexExcepts'] = './reports/'+now+'_indexExcepts.csv'

	# init worker, always with printOnly parameter, defaulting to localConfig unless explicitly set 
	worker = SolrIndexerWorker(printOnly=printOnly)

	# determine action based on fedEvent
	# Index single item per fedEvent
	if fedEvent == "modifyDatastreamByValue" or fedEvent == "ingest" or fedEvent == "modifyObject":

		print "Updating / Indexing",PID
		# index PIDs in Solr
		result = worker.indexFOXMLinSolr(PID,outputs)

		# printOnly, do not continue with updates
		if worker.printOnly == True:
			return result
			# return True
		
		# augment documents - from augmentCore.py
		augmentCore(PID)		
		return True


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

		# printOnly, do not continue with updates
		if worker.printOnly == True:
			return True

		# update timestamp in Solr		
		worker.updateLastFedoraIndexDate()
		# manually commit and replicate changes
		worker.commitSolrChanges()
		worker.replicateToSearch()

		print "Total seconds elapsed",worker.totalTime	
		return True	


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
		# close handle
		toUpdate.close()

		# printOnly, do not continue with updates
		if worker.printOnly == True:
			return True

		# update timestamp in Solr		
		worker.updateLastFedoraIndexDate()
		# manually commit and replicate changes
		worker.commitSolrChanges()
		worker.replicateToSearch()

		print "Total seconds elapsed",worker.totalTime	
		return True
		

	# Remove Object from Solr Index on Purge
	if fedEvent == "purgeObject":
		print "Removing the following from Solr Index",PID		
		worker.removeFOXMLinSolr(PID)
		return True


	# Replicate staging to production
	if fedEvent == "replicateStagingToProduction":
		print "replicating staging core to production"
		r = requests.get('http://localhost/solr4/search/replication?command=fetchindex&wt=json&commit=false')
		response = json.loads(r.content)
		if response['status'] == "OK":
			print "Success"
			return True
		else:
			print "Failure"
			return False


	# finally, commit all changes
	solr_manage_handle.commit()


if __name__ == '__main__':
	# running as OS script indexes all recently modified
	solrIndexer("timestampIndex","")
























