# utility to edit RELS-EXT datastream for objects

# handles
from fedoraManager2.forms import RDF_edit
from fedoraManager2.solrHandles import solr_handle
from fedoraManager2.fedoraHandles import fedora_handle
from fedoraManager2.jobs import getSelPIDs
from fedoraManager2 import models
from fedoraManager2 import db
from fedoraManager2.sensitive import *
from flask import Blueprint, render_template, abort, request

#python modules
from lxml import etree
import re
import requests
from requests.auth import HTTPBasicAuth
import json

# eulfedora
import eulfedora

# rdflib
from rdflib.compare import to_isomorphic, graph_diff


# blueprint creation
editRELSv2 = Blueprint('editRELSv2', __name__, template_folder='templates')


# @editRELSv2.route('/editRELSv2', methods=['POST', 'GET'])
# def index():

# 	# get PID to examine, if noted
# 	if request.args.get("PIDnum") != None:
# 		PIDnum = int(request.args.get("PIDnum"))		
# 	else:
# 		PIDnum = 0
	
# 	# get PIDs	
# 	PIDs = getSelPIDs()	
# 	print PIDs[PIDnum]	

# 	# get triples for 1st object
# 	riquery = fedora_handle.risearch.spo_search(subject="info:fedora/"+PIDs[PIDnum], predicate=None, object=None)
	
# 	# filter out RELS-EXT and WSUDOR predicates
# 	riquery_filtered = []
# 	for s,p,o in riquery:
# 		try:
# 			if "relations-external" in p or "WSUDOR-Fedora-Relations" in p:
# 				riquery_filtered.append((p,o))	
# 		except:
# 			print "Could not parse RDF relationship"
# 	riquery_filtered.sort() #mild sorting applied to group WSUDOR or RELS-EXT

# 	return render_template('old.html',riquery_filtered=riquery_filtered,PID=PIDs[PIDnum],PIDnum=PIDnum)

@editRELSv2.route('/editRELSv2', methods=['POST', 'GET'])
def index():	

	return render_template('editRELSv2_index.html')
	

@editRELSv2.route('/editRELSv2_shared', methods=['POST', 'GET'])
def shared():
	'''
	Will return only RDF statements shared (predicate AND object) by all PIDs	

	- Requires workaround for large queries...
		- Eulfedora (uses GET, too small)
		- POST requests 100+ break sparql
		- Solution: for scenarios with 100+ PIDs, break into smaller queries, then mix together in results

	'''

	# get PIDs	
	PIDs = getSelPIDs()	

	# shared relationships
	shared_relationships = []

	if len(PIDs) > 100:		

		def grouper(iterable, chunksize, fillvalue=None):
			from itertools import izip_longest
			args = [iter(iterable)] * chunksize
			return izip_longest(*args, fillvalue=fillvalue)

		chunks =  grouper(PIDs,100)

		for chunk in chunks:			

			# construct where statement for query
			where_statement = ""
			for PID in chunk:
				if PID != None:				
					where_statement += "<fedora:{PID}> $predicate $object . ".format(PID=PID)
			query_statement = "select $predicate $object from <#ri> where {{ {where_statement} }}".format(where_statement=where_statement)		

			# print query_statement
			
			base_URL = "http://localhost/fedora/risearch"
			payload = {
				"lang" : "sparql",
				"query" : query_statement,
				"flush" : "false",
				"type" : "tuples",
				"format" : "JSON"
			}
			r = requests.post(base_URL, auth=HTTPBasicAuth(username, password), data=payload )
			risearch = json.loads(r.text)
			for each in risearch['results']:
				if each not in shared_relationships:
					shared_relationships.append(each)

	else:
		# construct where statement for query
		where_statement = ""
		for PID in PIDs:
			where_statement += "<fedora:{PID}> $predicate $object . ".format(PID=PID)
		query_statement = "select $predicate $object from <#ri> where {{ {where_statement} }}".format(where_statement=where_statement)
		
		base_URL = "http://localhost/fedora/risearch"
		payload = {
			"lang" : "sparql",
			"query" : query_statement,
			"flush" : "false",
			"type" : "tuples",
			"format" : "JSON"
		}
		r = requests.post(base_URL, auth=HTTPBasicAuth(username, password), data=payload )
		risearch = json.loads(r.text)
		shared_relationships = risearch['results']
		
	print shared_relationships


	return render_template('editRELS_shared.html',shared_relationships=shared_relationships)












