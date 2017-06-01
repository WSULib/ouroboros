# small utility to edit RELS-EXT datastream for objects

# celery
from WSUDOR_Manager import celery
from celery import Task

# handles
from WSUDOR_Manager.forms import OAI_sets 
from WSUDOR_Manager.solrHandles import solr_handle
from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager.jobs import getSelPIDs
from WSUDOR_Manager import models
from WSUDOR_Manager import db
from WSUDOR_Manager import utilities, roles, logging
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
from subprocess import Popen, PIPE

import localConfig

manageOAI = Blueprint('manageOAI', __name__, template_folder='templates', static_folder="static")


@manageOAI.route('/manageOAI', methods=['POST', 'GET'])
@roles.auth(['admin','metadata','view'])
def index():	

	# example URL patterns
	example_url_patterns = {
		'Identify':'http://%s/api/oai?verb=Identify' % (localConfig.PUBLIC_HOST),
		'ListMetadataFormats':'http://%s/api/oai?verb=ListMetadataFormats' % (localConfig.PUBLIC_HOST),
		'ListIdentifiers':'http://%s/api/oai?verb=ListIdentifiers&metadataPrefix=mods' % (localConfig.PUBLIC_HOST),
		'GetRecord':'http://%s/api/oai?verb=GetRecord&identifier=oai:digital.library.wayne.edu:wayne:vmc14515&metadataPrefix=mods' % (localConfig.PUBLIC_HOST),
		'ListRecords':'http://%s/api/oai?verb=ListRecords&metadataPrefix=mods' % (localConfig.PUBLIC_HOST),
		'ListSets':'http://%s/api/oai?verb=ListSets' % (localConfig.PUBLIC_HOST),
	}


	# get all collections, to provide previews by collection
	all_collections = fedora_handle.risearch.sparql_query("select $dc_title $subject from <#ri> where { \
		$subject <http://purl.org/dc/elements/1.1/title> $dc_title . \
		$subject <fedora-rels-ext:hasContentModel> <info:fedora/CM:Collection> . \
		}")
	collection_tups = [ (rel["dc_title"],rel["subject"].split("/")[1]) for rel in all_collections]

	# get all OAI sets, via rels_isMemberOfOAISet relationship
	search_results = solr_handle.search(**{
			'q':'*:*',
			'fq':['rels_itemID:*','rels_isMemberOfOAISet:*'],
			'rows':0,
			'facet':True,
			'facet.field':'rels_isMemberOfOAISet'
		})

	# generate response
	set_tups = [(k,k) for k in search_results.facets['facet_fields']['rels_isMemberOfOAISet'].keys() if k.startswith('wayne')]

	return render_template("manageOAI_index.html", collection_tups=collection_tups, set_tups=set_tups, example_url_patterns=example_url_patterns, APP_HOST=localConfig.APP_HOST)


# expose objects to DPLA OAI-PMH set
@roles.auth(['admin','metadata'], is_celery=True)
def exposeToDPLA_worker(job_package):

	logging.debug("adding to DPLAOAI set")

	# get PID
	PID = job_package['PID']		
	obj_ohandle = fedora_handle.get_object(PID)

	# add relationship
	return obj_ohandle.add_relationship("http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isMemberOfOAISet", "info:fedora/wayne:collectionDPLAOAI")


# remove objects to DPLA OAI-PMH set
@roles.auth(['admin','metadata'], is_celery=True)
def removeFromDPLA_worker(job_package):

	logging.debug("purging from DPLAOAI set")

	# get PID
	PID = job_package['PID']		
	obj_ohandle = fedora_handle.get_object(PID)	

	# add relationship
	return obj_ohandle.purge_relationship("http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isMemberOfOAISet", "info:fedora/wayne:collectionDPLAOAI")
	




















	


