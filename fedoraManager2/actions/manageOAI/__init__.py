# small utility to edit RELS-EXT datastream for objects

# handles
from fedoraManager2.forms import OAI_sets 
from fedoraManager2.solrHandles import solr_handle
from fedoraManager2.fedoraHandles import fedora_handle
from fedoraManager2.jobs import getSelPIDs
from fedoraManager2 import models
from fedoraManager2 import db
from fedoraManager2 import utilities
from fedoraManager2.sensitive import *
from flask import Blueprint, render_template, abort, request, redirect

#python modules
from lxml import etree
import re
import requests
from requests.auth import HTTPBasicAuth
import json

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

	OAI_sets_tuples = utilities.returnOAISets('detailed')

	# finally, find all currently available / defined sets
	# instantiate forms
	form = OAI_sets()

	return render_template("manageOAI_serverWide.html",OAI_sets_tuples=OAI_sets_tuples,form=form)


@manageOAI.route('/manageOAI/objectRelated', methods=['POST', 'GET'])
def objectRelated():

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
				where_statement += "<fedora:{PID}> <http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isMemberOfOAISet> $object . $object <http://www.openarchives.org/OAI/2.0/setSpec> $setSpec . $object <http://www.openarchives.org/OAI/2.0/setName> $setName .".format(PID=PID)
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
				tup = (each['object'],each['setSpec'], each['setName'])
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
		shared_relationships = [ (each['object'],each['setSpec'], each['setName']) for each in risearch['results'] ]

	print shared_relationships

	# finally, find all currently available / defined sets
	# instantiate forms
	form = OAI_sets()


	return render_template("manageOAI_objectRelated.html",shared_relationships=shared_relationships,form=form)

def manageOAI_genItemID_worker(job_package):

	# get PID
	PID = job_package['PID']		
	obj_ohandle = fedora_handle.get_object(PID)	

	# generate OAI identifier
	OAI_identifier = "oai:digital.library.wayne.edu:{PID}".format(PID=PID)	
	
	print obj_ohandle.add_relationship("http://www.openarchives.org/OAI/2.0/itemID", OAI_identifier)
	

def manageOAI_addSet_worker(job_package):

	# get PID
	PID = job_package['PID']		
	obj_ohandle = fedora_handle.get_object(PID)

	form_data = job_package['form_data']
	target_collection_object = form_data['obj'].encode('utf-8').strip()
		
	print obj_ohandle.add_relationship("http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isMemberOfOAISet", target_collection_object )


# Boutique Jobs
@manageOAI.route('/manageOAI/purgeSet', methods=['POST', 'GET'])
def manageOAI_purgeSet_worker():
	# small utility to remove OAI set definitions from collection objects
	# boutique, not coming through normal channels

	form_data = request.form
	print form_data

	# get object handle
	PID = form_data['obj']
	obj_ohandle = fedora_handle.get_object(PID)
	
	# purge setSpec relationship
	success = True
	while success == True:
		predicate_string = "http://www.openarchives.org/OAI/2.0/setSpec"
		object_string = form_data['setSpec'].encode('utf-8').strip()
		print obj_ohandle.purge_relationship(predicate_string, object_string)

		# purge setName relationship
		predicate_string = "http://www.openarchives.org/OAI/2.0/setName"
		object_string = form_data['setName'].encode('utf-8').strip()
		print obj_ohandle.purge_relationship(predicate_string, object_string)	

		return "Collection removed as OAI set."

	return "Collection could not be removed, errors were had." 
	

@manageOAI.route('/manageOAI/createSet', methods=['POST', 'GET'])
def manageOAI_createSet_worker():
	# small utility to remove OAI set definitions from collection objects
	# boutique, not coming through normal channels

	form_data = request.form
	print form_data

	# get object handle
	PID = form_data['obj_PID']
	obj_ohandle = fedora_handle.get_object(PID)
	
	# purge setSpec relationship
	# success = True
	# while success == True:
	predicate_string = "http://www.openarchives.org/OAI/2.0/setSpec"
	object_string = form_data['setSpec'].encode('utf-8').strip()
	print obj_ohandle.add_relationship(predicate_string, object_string)

	# purge setName relationship
	predicate_string = "http://www.openarchives.org/OAI/2.0/setName"
	object_string = form_data['setName'].encode('utf-8').strip()
	print obj_ohandle.add_relationship(predicate_string, object_string)	

	return redirect("/tasks/manageOAI/serverWide")

	
	
	
























