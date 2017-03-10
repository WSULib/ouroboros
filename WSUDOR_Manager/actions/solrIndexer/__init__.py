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
from flask import Blueprint, render_template, make_response, abort, request, redirect
import json

# celery
from WSUDOR_Manager import celery
from celery import Task

# WSUDOR
from localConfig import *
from WSUDOR_Manager.solrHandles import solr_handle
from WSUDOR_Manager.fedoraHandles import fedora_handle
import WSUDOR_ContentTypes
from WSUDOR_Manager import models, jobs, helpers, roles
import WSUDOR_Manager.actions as actions

# augmentCore 
from augmentCore import augmentCore

import localConfig

# define blueprint
solrIndexer_blue = Blueprint('solrIndexer', __name__, template_folder='templates')




'''
As this needs to run via curl command, removing roles temporarily.
'''
@solrIndexer_blue.route("/updateSolr/<update_type>", methods=['POST', 'GET'])
# @roles.auth(['admin','metadata'])
def updateSolr(update_type):	


	# Experimental: build human_hash
	'''
	Whenever updateSolr() is run, which has the potential of iterating over one or thousands of PIDs,
	query Solr and generate a map of human titles to PIDs for select fields.  This is used during the 
	index process to set human readable fields with the prefix: human_*

	For example, 'info:fedora/wayne:collectionvmc' = 'Virtual Motor City Collection'
	'''
	human_hash = gen_human_hash()

	# real or emulated solr events
	if update_type == "fullIndex":

		if 'choice' not in request.form:
			return render_template('confirm.html',update_type=update_type)
		else:
			# fire only with confirmation
			if "choice" in request.form and request.form['choice'] == "confirm" and request.form['confirm_string'].lower() == 'confirm':		
				index_handle = solrIndexer.delay('fullIndex', None, human_hash=human_hash)
			else:
				print 'skipping fullIndex'
				return redirect('/tasks/updateSolr/select')


	if update_type == "timestamp":
		print "Updating by timestamp"	
		index_handle = solrIndexer.delay('timestampIndex', None, human_hash=human_hash)


	if update_type == "userObjects":
		print "Updating by userObjects"	
		PIDs = jobs.getSelPIDs()
		for PID in PIDs:
			index_handle = solrIndexer.delay('modifyObject', PID, human_hash=human_hash)	


	# purge and reindex fedobjs (SLOW)
	if update_type == "purgeAndFullIndex":

		if 'choice' not in request.form:
			return render_template('confirm.html',update_type=update_type)

		else:

			# fire only with confirmation
			if "choice" in request.form and request.form['choice'] == "confirm" and request.form['confirm_string'].lower() == 'confirm':

				print "Purging solr core and reindexing all objects"
				# delete all from /fedobjs core
				if 'fedobjs' in solr_handle.base_url:
					solr_handle.delete_by_query('*:*',commit=False)
				# run full index	
				index_handle = solrIndexer.delay('fullIndex', None, human_hash=human_hash)

			else:
				print 'skipping purge and index'
				return redirect('/tasks/updateSolr/select')

	
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
	def __init__(self, printOnly, human_hash):
		self.startTime = int(time.time())
		self.printOnly = printOnly
		self.human_hash = human_hash

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
		
		risearch_query = "select $object from <#ri> where $object <info:fedora/fedora-system:def/model#hasModel> <info:fedora/fedora-system:FedoraObject-3.0> and $object <fedora-view:lastModifiedDate> $modified and $modified <mulgara:after> '%s'^^<xml-schema:dateTime> in <#xsd>" % (lastFedoraIndexDate)

		risearch_params = urllib.urlencode({
			'type': 'tuples', 
			'lang': 'itql', 
			'format': 'CSV',
			'limit':'',
			'dt': 'on',
			'stream':'on',
			'query': risearch_query
			})
		risearch_host = "http://%s:%s@localhost/fedora/risearch?" % (FEDORA_USER, FEDORA_PASSWORD)

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

		# re-derive Dublin Core metadata if MODS has changed
		try:
			obj_handle.DCfromMODS()
		except:
			print "could not re-derive DC from MODS"

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
			size_dict = obj_handle.object_size()
			setattr(obj_handle.SolrDoc.doc, "obj_size_fedora_i", size_dict['fedora_total_size'][0] )
			setattr(obj_handle.SolrDoc.doc, "obj_size_fedora_human", size_dict['fedora_total_size'][1] )
			setattr(obj_handle.SolrDoc.doc, "obj_size_wsudor_i", size_dict['wsudor_total_size'][0] )
			setattr(obj_handle.SolrDoc.doc, "obj_size_wsudor_human", size_dict['wsudor_total_size'][1] )
		except:
			print "Could not determine object size, skipping"


		#######################################################################################
		# Here, we have the opportunity to do some cleanup, addition, and finagling of fields.
		#######################################################################################

		print self.human_hash

		# derive human readable fields, 'human_*'
		collections = getattr(obj_handle.SolrDoc.doc, 'rels_isMemberOfCollection', False)
		if collections:
			print "deriving human collection names"
			print collections
			for pid in collections:
				pid = pid.split("/")[1]
				if pid in self.human_hash['collections']:
					setattr(obj_handle.SolrDoc.doc, "human_isMemberOfCollection", self.human_hash['collections'][pid] )


		content_types = getattr(obj_handle.SolrDoc.doc, 'rels_hasContentModel', False)
		if content_types:
			print "deriving human content types"
			print content_types
			for pid in content_types:
				pid = pid.split("/")[1]
				if pid in self.human_hash['content_types']:
					setattr(obj_handle.SolrDoc.doc, "human_hasContentModel", self.human_hash['content_types'][pid] )

		
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
		result = solr_handle.commit()
		print result
		return result

	
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
def solrIndexer(index_type, PID, human_hash=False, printOnly=SOLR_INDEXER_WRITE_DEFAULT):

	print "solrIndexer running for index_type %s" % index_type

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
	if not human_hash:
		print "human_hash not found, generating..."
		human_hash = gen_human_hash()

	worker = SolrIndexerWorker(printOnly, human_hash)

	# determine action based on index_type
	# Index single item per index_type
	if index_type in ["ingest", "modifyObject","WSUDOR_Indexer"]:

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
	if index_type == "timestampIndex":

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

		print "Total seconds elapsed",worker.totalTime	
		return True	


	# fullindex
	if index_type == "fullIndex":
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
		
		print "Total seconds elapsed",worker.totalTime	
		return True
		

	# Remove Object from Solr Index on Purge
	if index_type == "purgeObject":
		print "Removing the following from Solr Index",PID		
		worker.removeFOXMLinSolr(PID)
		return True


	# finally, commit all changes
	print "committing changes"
	solr_handle.commit()


def gen_human_hash():
	print "preparing 'human_hash' values..."
	return {
		'collections': { doc['id']: doc['dc_title'][0] for doc in solr_handle.search(**{'q':'rels_hasContentModel\:info\:fedora/CM\:Collection','fl':'id dc_title','rows':1000}).documents },
		'content_types': { doc['id']: doc['dc_title'][0] for doc in solr_handle.search(**{'q':'rels_hasContentModel\:info\:fedora/CM\:ContentModel','fl':'id dc_title','rows':1000}).documents }
	}


if __name__ == '__main__':
	# running as OS script indexes all recently modified
	solrIndexer("timestampIndex","")
























