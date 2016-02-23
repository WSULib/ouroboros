# small utility to edit RELS-EXT datastream for objects

# celery
from cl.cl import celery
from celery import Task

# handles
from WSUDOR_Manager.forms import OAI_sets 
from WSUDOR_Manager.solrHandles import solr_handle
from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager.jobs import getSelPIDs
from WSUDOR_Manager import models
from WSUDOR_Manager import db
from WSUDOR_Manager import utilities
from localConfig import *
from WSUDOR_Manager import redisHandles
from flask import Blueprint, render_template, abort, request, redirect

#python modules
from lxml import etree
import re
import requests
from requests.auth import HTTPBasicAuth
import json
import time
import os
import shutil
import _mysql

# eulfedora
import eulfedora

# local
from tomcat_manager import *

import localConfig

manageOAI = Blueprint('manageOAI', __name__, template_folder='templates', static_folder="static")

'''
REFERENCE
baseURL: http://digital.library.wayne.edu:8080/oaiprovider/
ListIdentifiers: http://digital.library.wayne.edu:8080/oaiprovider/?verb=ListIdentifiers&metadataPrefix=oai_dc
'''

@manageOAI.route('/manageOAI', methods=['POST', 'GET'])
def index():	

	overview = {}

	# connect to DB
	con = _mysql.connect('localhost','WSUDOR_Manager','WSUDOR_Manager','proai')
	
	# total items
	con.query('SELECT * FROM rcItem')
	t_results = con.store_result()
	overview['total_count'] = t_results.num_rows()

	# total items harvested by REPOX under DPLAOAI set
	con.query("SELECT rcItem.identifier AS pid FROM rcItem INNER JOIN rcRecord ON rcItem.itemKey = rcRecord.itemKey INNER JOIN rcMembership ON rcMembership.recordKey = rcRecord.recordKey INNER JOIN rcSet ON rcSet.setKey = rcMembership.setKey INNER JOIN rcFormat ON rcFormat.formatKey = rcRecord.formatKey WHERE rcFormat.mdPrefix = 'mods' AND rcSet.setSpec = 'set:wayne:collectionDPLAOAI'")
	repox_results = con.store_result()
	overview['repox_count'] = repox_results.num_rows()

	# metadata prefixes
	con.query('SELECT mdPrefix, namespaceURI, schemaLocation FROM rcFormat')
	results = con.use_result()
	overview['metas'] = []
	while True:
		record = results.fetch_row()
		if not record:
			break
		overview['metas'].append(record[0])

	# sets prefixes
	con.query('SELECT setSpec FROM rcSet')
	results = con.use_result()
	overview['sets'] = []
	while True:
		record = results.fetch_row()
		if not record:
			break
		overview['sets'].append(record[0][0])

	# get status of Tomcat webapp
	tm = TomcatManager(url="http://localhost:8080/manager/text", userid=TOMCAT_USER, password=TOMCAT_PASSWORD)
	for each in tm.list():
		if each[0] == TOMCAT_PROAI_PATH:
			overview['webapp_status'] = each[1]


	# total items
	con.query('SELECT * FROM rcQueue')
	q_results = con.store_result()
	overview['queue_count'] = q_results.num_rows()
	if overview['queue_count'] > 0:
		print "PROAI has queue, still syncing..."
		

	# DEBUG
	# print overview
	
	return render_template("manageOAI_index.html", overview=overview, APP_HOST=localConfig.APP_HOST)

@manageOAI.route('/manageOAI/serverWide', methods=['POST', 'GET'])
def serverWide():	

	# get all collections and collection titles
	all_collections = fedora_handle.risearch.sparql_query("select $dc_title $subject $isOAIHarvestable from <#ri> where { \
		$subject <http://purl.org/dc/elements/1.1/title> $dc_title . \
		$subject <fedora-rels-ext:hasContentModel> <info:fedora/CM:Collection> . \
		$subject <http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isOAIHarvestable> $isOAIHarvestable \
		}")
	
	collection_tups = [ (rel["dc_title"],rel["subject"].split("/")[1],rel["isOAIHarvestable"]) for rel in all_collections]	

	return render_template("manageOAI_serverWide.html",collection_tups=collection_tups,APP_HOST=localConfig.APP_HOST)


@manageOAI.route('/manageOAI/objectRelated', methods=['POST', 'GET'])
@utilities.objects_needed
def objectRelated():

	# from WSUDOR_Manager import forms

	# '''
	# Query to see what will show up in REPOX:
	# SELECT rcItem.identifier AS pid FROM rcItem INNER JOIN rcRecord ON rcItem.itemKey = rcRecord.itemKey INNER JOIN rcMembership ON rcMembership.recordKey = rcRecord.recordKey INNER JOIN rcSet ON rcSet.setKey = rcMembership.setKey INNER JOIN rcFormat ON rcFormat.formatKey = rcRecord.formatKey WHERE rcFormat.mdPrefix = 'mods' AND rcSet.setSpec = 'set:wayne:collectionDPLAOAI';
	# '''

	# # get PIDs	
	# PIDs = getSelPIDs()

	# # shared_relationships (in this instance, the PID of collection objects these assert membership to)	
	# shared_relationships = []

	# # function for shared query between whole and chunked queries
	# def risearchQuery(list_of_PIDs):
	# 	# construct where statement for query
	# 	where_statement = ""
	# 	for PID in list_of_PIDs:
	# 		if PID != None:				
	# 			where_statement += "<fedora:{PID}> <http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isMemberOfOAISet> $object . $object <http://www.openarchives.org/OAI/2.0/setSpec> $setSpec . $object <http://www.openarchives.org/OAI/2.0/setName> $setName .".format(PID=PID)
	# 	query_statement = "select $object $setSpec $setName from <#ri> where {{ {where_statement} }}".format(where_statement=where_statement)		
	# 	base_URL = "http://{FEDORA_USER}:{FEDORA_PASSWORD}@localhost/fedora/risearch".format(FEDORA_USER=FEDORA_USER,FEDORA_PASSWORD=FEDORA_PASSWORD)
	# 	payload = {
	# 		"lang" : "sparql",
	# 		"query" : query_statement,
	# 		"flush" : "false",
	# 		"type" : "tuples",
	# 		"format" : "JSON"
	# 	}
	# 	r = requests.post(base_URL, auth=HTTPBasicAuth(FEDORA_USER, FEDORA_PASSWORD), data=payload )
	# 	risearch = json.loads(r.text)
	# 	return risearch	

	# # if more than 100 PIDs, chunk into sub-queries
	# if len(PIDs) > 100:
	# 	def grouper(iterable, chunksize, fillvalue=None):
	# 		from itertools import izip_longest
	# 		args = [iter(iterable)] * chunksize
	# 		return izip_longest(*args, fillvalue=fillvalue)

	# 	chunks =  grouper(PIDs,100)

	# 	for chunk in chunks:

	# 		# perform query
	# 		risearch = risearchQuery(chunk)

	# 		chunk_list = []			
	# 		for each in risearch['results']:
	# 			tup = (each['object'].split("/")[1],each['setSpec'], each['setName'])
	# 			chunk_list.append(tup)
	# 		try:
	# 			curr_set = set.intersection(curr_set,set(chunk_list))
	# 		except:
	# 			curr_set = set(chunk_list)

	# 	print curr_set
	# 	shared_relationships = curr_set		

	# else:		
	# 	# perform query
	# 	risearch = risearchQuery(PIDs)
	# 	shared_relationships = [ (each['object'].split("/")[1],each['setSpec'], each['setName']) for each in risearch['results'] ]

	# print shared_relationships

	# # finally, find all currently available / defined sets	
	# form = forms.OAI_sets()
	# active_sets = utilities.returnOAISets('dropdown')
	# total_sets = len(active_sets)

	# return render_template("manageOAI_objectRelated.html",shared_relationships=shared_relationships,form=form,active_sets=active_sets,total_sets=total_sets)

	return render_template("manageOAI_objectRelated.html")

# generate OAI identifiers for objects
def manageOAI_genItemID_worker(job_package):
	
	# get PID
	PID = job_package['PID']		
	obj_ohandle = fedora_handle.get_object(PID)	

	# generate OAI identifier
	OAI_identifier = "oai:digital.library.wayne.edu:%s" % (PID)	
	
	print obj_ohandle.add_relationship("http://www.openarchives.org/OAI/2.0/itemID", OAI_identifier)
	
@manageOAI.route('/manageOAI/toggleSet/<PID>', methods=['POST', 'GET'])
def manageOAI_toggleSet(PID):	

	isOAIHarvestable_predicate = "http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isOAIHarvestable"
	
	# determine collection status
	obj_ohandle = fedora_handle.get_object(PID)
	harvest_status_gen = obj_ohandle.risearch.get_objects(obj_ohandle.uriref, isOAIHarvestable_predicate)
	harvest_status = harvest_status_gen.next()	

	# get collection name
	dc_title_gen = obj_ohandle.risearch.get_objects(obj_ohandle.uriref,"dc:title")
	dc_title = dc_title_gen.next()

	# toggle collection OAI relatedd RELS-EXT relationships	
	if harvest_status == "False":
		print "Object was not harvestable, enabling..."
		print obj_ohandle.modify_relationship(isOAIHarvestable_predicate, "False", "True")	
		toggle_function = obj_ohandle.add_relationship
	if harvest_status == "True":
		print "Object was harvestable, deactivating..."
		print obj_ohandle.modify_relationship(isOAIHarvestable_predicate, "True", "False")	
		toggle_function = obj_ohandle.purge_relationship
		
	# setSpec relationship	
	predicate_string = "http://www.openarchives.org/OAI/2.0/setSpec"
	object_string = "set:%s" % (PID)
	print toggle_function(predicate_string, object_string)

	# setName relationship	
	predicate_string = "http://www.openarchives.org/OAI/2.0/setName"
	object_string = dc_title
	print toggle_function(predicate_string, object_string)


	# toggle relationships for child objects (runs as celery task)	
	# collection_objects = obj_ohandle.risearch.get_subjects("fedora-rels-ext:isMemberOfCollection",obj_ohandle.uriref)	
	# for object_uri in collection_objects:
	# 	manageOAI_toggleSet_worker.delay(harvest_status,object_uri,PID)

	return redirect("/tasks/manageOAI/serverWide")	

# Fires *after* task is complete
class postTask(Task):
	abstract = True
	def after_return(self, *args, **kwargs):
		task_details = args[3]			
		object_uri = task_details[1]
		PID = object_uri.split("/")[1]
		# release PID from PIDlock
		redisHandles.r_PIDlock.delete(PID)


# celery function, runs through normal channels
@celery.task(base=postTask, bind=True, max_retries=100, name="manageOAI_toggleSet_worker")
def manageOAI_toggleSet_worker(self,harvest_status,object_uri,collectionPID):
	PID = object_uri.split("/")[1]

	################################################	
	# check PIDlock	
	lock_status = redisHandles.r_PIDlock.exists(PID)
	
	# if locked, divert
	if lock_status == True:
		time.sleep(.25)
		raise self.retry(countdown=3)
	else:
		redisHandles.r_PIDlock.set(PID,1)
	################################################

	isMemberOfOAISet_predicate = "http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isMemberOfOAISet"
	obj_handle = fedora_handle.get_object(object_uri)

	# toggle collection OAI relatedd RELS-EXT relationships	
	if harvest_status == "False":
		print "%s was not part of set, enabling..." % (PID)		
		toggle_function = obj_handle.add_relationship
	if harvest_status == "True":
		print "%s was harvestable, deactivating..." % (PID)		
		toggle_function = obj_handle.purge_relationship
		
	# isMemberOfOAISet relationship		
	predicate_string = isMemberOfOAISet_predicate
	object_string = "info:fedora/%s" % (collectionPID)
	return toggle_function(predicate_string, object_string)


@manageOAI.route('/manageOAI/purgePROAI', methods=['POST', 'GET'])
def purgePROAI():

	'''
	Our PROAI server operates under the Tomcat Webapp path '/oaiprovider'
	'''

	PROAI_TABLES = [
		'rcAdmin',         
		'rcFailure',       
		'rcFormat',        
		'rcItem',          
		'rcMembership',    
		'rcPrunable',      
		'rcQueue',         
		'rcRecord',        
		'rcSet' 
	]
	
	# connect to Tomcat
	tm = TomcatManager(url="http://localhost:8080/manager/text", userid=TOMCAT_USER, password=TOMCAT_PASSWORD)

	# stop PROAI (gets path from localConfig.py)
	print "Stopping PROAI"
	tm.stop(TOMCAT_PROAI_PATH)

	# purge disc cache
	print "Delete cache"
	os.system('rm -r %s/*' % (PROAI_CACHE_LOCATION))	

	# truncate MySQL tables
	con = _mysql.connect('localhost','WSUDOR_Manager','WSUDOR_Manager','proai')
	for table in PROAI_TABLES:
		print "Deleting rows from",table
		con.query('DELETE FROM %s' % (table))
	con.close()

	# restart PROAI
	print "Starting PROAI"
	tm.start(TOMCAT_PROAI_PATH)

	return redirect("/tasks/manageOAI")


# expose objects to DPLA OAI-PMH set
def exposeToDPLA_worker(job_package):

	# get PID
	PID = job_package['PID']		
	obj_ohandle = fedora_handle.get_object(PID)	

	# add relationship
	return obj_ohandle.add_relationship("http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isMemberOfOAISet", "info:fedora/wayne:collectionDPLAOAI")# expose 


# remove objects to DPLA OAI-PMH set
def removeFromDPLA_worker(job_package):

	# get PID
	PID = job_package['PID']		
	obj_ohandle = fedora_handle.get_object(PID)	

	# add relationship
	return obj_ohandle.purge_relationship("http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isMemberOfOAISet", "info:fedora/wayne:collectionDPLAOAI")
	




















	


