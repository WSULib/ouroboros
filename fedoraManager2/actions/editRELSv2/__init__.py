# utility to edit RELS-EXT datastream for objects

# handles
from fedoraManager2.forms import RDF_edit
from fedoraManager2.solrHandles import solr_handle
from fedoraManager2.fedoraHandles import fedora_handle
from fedoraManager2.jobs import getSelPIDs
from fedoraManager2 import models
from fedoraManager2 import db
from flask import Blueprint, render_template, abort, request

#python modules
from lxml import etree
import re
import requests

# eulfedora
import eulfedora

# rdflib
from rdflib.compare import to_isomorphic, graph_diff


# blueprint creation
editRELSv2 = Blueprint('editRELSv2', __name__, template_folder='templates', static_folder="static")


@editRELSv2.route('/editRELSv2', methods=['POST', 'GET'])
def index():

	# get PID to examine, if noted
	if request.args.get("PIDnum") != None:
		PIDnum = int(request.args.get("PIDnum"))		
	else:
		PIDnum = 0
	
	# get PIDs	
	PIDs = getSelPIDs()	
	print PIDs[PIDnum]

	# instantiate forms
	form = RDF_edit()		

	# get triples for 1st object
	riquery = fedora_handle.risearch.spo_search(subject="info:fedora/"+PIDs[PIDnum], predicate=None, object=None)
	
	# filter out RELS-EXT and WSUDOR predicates
	riquery_filtered = []
	for s,p,o in riquery:
		try:
			if "relations-external" in p or "WSUDOR-Fedora-Relations" in p:
				riquery_filtered.append((p,o))	
		except:
			print "Could not parse RDF relationship"
	riquery_filtered.sort() #mild sorting applied to group WSUDOR or RELS-EXT

	return render_template('editRELS_indexv2.html',riquery_filtered=riquery_filtered,PID=PIDs[PIDnum],PIDnum=PIDnum)
	
























	