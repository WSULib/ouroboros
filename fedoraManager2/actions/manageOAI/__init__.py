# small utility to edit RELS-EXT datastream for objects

# celery
from cl.cl import celery
from celery import Task

# handles
from fedoraManager2.forms import OAI_sets 
from fedoraManager2.solrHandles import solr_handle
from fedoraManager2.fedoraHandles import fedora_handle
from fedoraManager2.jobs import getSelPIDs
from fedoraManager2 import models
from fedoraManager2 import db
from fedoraManager2 import utilities
from localConfig import *
from fedoraManager2 import redisHandles
from flask import Blueprint, render_template, abort, request, redirect

#python modules
from lxml import etree
import re
import requests
from requests.auth import HTTPBasicAuth
import json
import time

# eulfedora
import eulfedora

manageOAI = Blueprint('manageOAI', __name__, template_folder='templates', static_folder="static")

'''
REFERENCE
baseURL: http://digital.library.wayne.edu:8080/oaiprovider/
ListIdentifiers: http://digital.library.wayne.edu:8080/oaiprovider/?verb=ListIdentifiers&metadataPrefix=oai_dc
'''

@manageOAI.route('/manageOAI', methods=['POST', 'GET'])
def index():	

	
	
	return render_template("manageOAI_index.html")

@manageOAI.route('/manageOAI/serverWide', methods=['POST', 'GET'])
def serverWide():	

	# get all collections and collection titles
	all_collections = fedora_handle.risearch.sparql_query("select $dc_title $subject $isOAIHarvestable from <#ri> where { \
		$subject <http://purl.org/dc/elements/1.1/title> $dc_title . \
		$subject <fedora-rels-ext:hasContentModel> <info:fedora/CM:Collection> . \
		$subject <http://silo.lib.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isOAIHarvestable> $isOAIHarvestable \
		}")
	
	collection_tups = [ (rel["dc_title"],rel["subject"].split("/")[1],rel["isOAIHarvestable"]) for rel in all_collections]	

	return render_template("manageOAI_serverWide.html",collection_tups=collection_tups)


@manageOAI.route('/manageOAI/objectRelated', methods=['POST', 'GET'])
def objectRelated():

	from fedoraManager2 import forms

	# get PIDs	
	PIDs = getSelPIDs()

	# shared_relationships (in this instance, the PID of collection objects these assert membership to)	
	shared_relationships = []

	# function for shared query between whole and chunked queries
	def risearchQuery(list_of_PIDs):
		# construct where statement for query
		where_statement = ""
		for PID in list_of_PIDs:
			if PID != None:				
				where_statement += "<fedora:{PID}> <http://silo.lib.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isMemberOfOAISet> $object . $object <http://www.openarchives.org/OAI/2.0/setSpec> $setSpec . $object <http://www.openarchives.org/OAI/2.0/setName> $setName .".format(PID=PID)
		query_statement = "select $object $setSpec $setName from <#ri> where {{ {where_statement} }}".format(where_statement=where_statement)		
		base_URL = "http://localhost/fedora/risearch"
		payload = {
			"lang" : "sparql",
			"query" : query_statement,
			"flush" : "false",
			"type" : "tuples",
			"format" : "JSON"
		}
		r = requests.post(base_URL, auth=HTTPBasicAuth(FEDORA_USER, FEDORA_PASSWORD), data=payload )
		risearch = json.loads(r.text)
		return risearch	

	# if more than 100 PIDs, chunk into sub-queries
	if len(PIDs) > 100:
		def grouper(iterable, chunksize, fillvalue=None):
			from itertools import izip_longest
			args = [iter(iterable)] * chunksize
			return izip_longest(*args, fillvalue=fillvalue)

		chunks =  grouper(PIDs,100)

		for chunk in chunks:

			# perform query
			risearch = risearchQuery(chunk)

			chunk_list = []			
			for each in risearch['results']:
				tup = (each['object'].split("/")[1],each['setSpec'], each['setName'])
				chunk_list.append(tup)
			try:
				curr_set = set.intersection(curr_set,set(chunk_list))
			except:
				curr_set = set(chunk_list)

		print curr_set
		shared_relationships = curr_set		

	else:		
		# perform query
		risearch = risearchQuery(PIDs)
		shared_relationships = [ (each['object'].split("/")[1],each['setSpec'], each['setName']) for each in risearch['results'] ]

	print shared_relationships

	# finally, find all currently available / defined sets	
	form = forms.OAI_sets()
	active_sets = utilities.returnOAISets('dropdown')
	total_sets = len(active_sets)


	return render_template("manageOAI_objectRelated.html",shared_relationships=shared_relationships,form=form,active_sets=active_sets,total_sets=total_sets)

# generate OAI identifiers for objects
def manageOAI_genItemID_worker(job_package):
	'''
	NOTE: This is really a one-way trip.  For multiple reaons:
		- Though this RELS-EXT relationship can be removed, it is extra work to extradite the from PROAI.
		- It is possible they have been harvested by virtue of being indexed in PROAI, lost control at that point.
	'''
	# get PID
	PID = job_package['PID']		
	obj_ohandle = fedora_handle.get_object(PID)	

	# generate OAI identifier
	OAI_identifier = "oai:digital.library.wayne.edu:{PID}".format(PID=PID)	
	
	print obj_ohandle.add_relationship("http://www.openarchives.org/OAI/2.0/itemID", OAI_identifier)
	
@manageOAI.route('/manageOAI/toggleSet/<PID>', methods=['POST', 'GET'])
def manageOAI_toggleSet(PID):	

	isOAIHarvestable_predicate = "http://silo.lib.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isOAIHarvestable"
	
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
	object_string = "set:{PID}".format(PID=PID)
	print toggle_function(predicate_string, object_string)

	# setName relationship	
	predicate_string = "http://www.openarchives.org/OAI/2.0/setName"
	object_string = dc_title
	print toggle_function(predicate_string, object_string)


	# toggle relationships for child objects (runs as celery task)	
	collection_objects = obj_ohandle.risearch.get_subjects("fedora-rels-ext:isMemberOfCollection",obj_ohandle.uriref)	
	for object_uri in collection_objects:
		manageOAI_toggleSet_worker.delay(harvest_status,object_uri,PID)

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

# celery function, runs through normal chanells
@celery.task(base=postTask,bind=True,max_retries=100,name="manageOAI_toggleSet_worker")
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

	isMemberOfOAISet_predicate = "http://silo.lib.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isMemberOfOAISet"
	obj_handle = fedora_handle.get_object(object_uri)

	# toggle collection OAI relatedd RELS-EXT relationships	
	if harvest_status == "False":
		print "{PID} was not part of set, enabling...".format(PID=PID)		
		toggle_function = obj_handle.add_relationship
	if harvest_status == "True":
		print "{PID} was harvestable, deactivating...".format(PID=PID)		
		toggle_function = obj_handle.purge_relationship
		
	# isMemberOfOAISet relationship		
	predicate_string = isMemberOfOAISet_predicate
	object_string = "info:fedora/{collectionPID}".format(collectionPID=collectionPID)	
	return toggle_function(predicate_string, object_string)



	



# def manageOAI_addSet_worker(job_package):

# 	# get PID
# 	PID = job_package['PID']		
# 	obj_ohandle = fedora_handle.get_object(PID)

# 	form_data = job_package['form_data']
# 	target_collection_object = form_data['obj'].encode('utf-8').strip()
		
# 	print obj_ohandle.add_relationship("http://silo.lib.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isMemberOfOAISet", target_collection_object )


# # Boutique Jobs
# @manageOAI.route('/manageOAI/purgeSet', methods=['POST', 'GET'])
# def manageOAI_purgeSet_worker():
	
# 	form_data = request.form
# 	print form_data

# 	# get object handle
# 	PID = form_data['obj']
# 	obj_ohandle = fedora_handle.get_object(PID)
	
# 	# purge setSpec relationship
# 	success = True
# 	while success == True:
# 		predicate_string = "http://www.openarchives.org/OAI/2.0/setSpec"
# 		object_string = form_data['setSpec'].encode('utf-8').strip()
# 		print obj_ohandle.purge_relationship(predicate_string, object_string)

# 		# purge setName relationship
# 		predicate_string = "http://www.openarchives.org/OAI/2.0/setName"
# 		object_string = form_data['setName'].encode('utf-8').strip()
# 		print obj_ohandle.purge_relationship(predicate_string, object_string)	

# 		return "Collection removed as OAI set."

# 	return "Collection could not be removed, errors were had." 
	

# @manageOAI.route('/manageOAI/createSet', methods=['POST', 'GET'])
# def manageOAI_createSet_worker():
# 	# small utility to remove OAI set definitions from collection objects
# 	# boutique, not coming through normal channels

# 	form_data = request.form
# 	print form_data

# 	# get object handle
# 	PID = form_data['obj_PID']
# 	obj_ohandle = fedora_handle.get_object(PID)
	
# 	# purge setSpec relationship
# 	# success = True
# 	# while success == True:
# 	predicate_string = "http://www.openarchives.org/OAI/2.0/setSpec"
# 	object_string = form_data['setSpec'].encode('utf-8').strip()
# 	print obj_ohandle.add_relationship(predicate_string, object_string)

# 	# purge setName relationship
# 	predicate_string = "http://www.openarchives.org/OAI/2.0/setName"
# 	object_string = form_data['setName'].encode('utf-8').strip()
# 	print obj_ohandle.add_relationship(predicate_string, object_string)	

# 	return redirect("/tasks/manageOAI/serverWide")


















