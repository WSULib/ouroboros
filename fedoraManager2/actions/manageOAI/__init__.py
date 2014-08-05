# small utility to edit RELS-EXT datastream for objects

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

# fuzzy matching lib
from fuzzywuzzy import fuzz

manageOAI = Blueprint('manageOAI', __name__, template_folder='templates', static_folder="static")

'''
REFERENCE
baseURL: http://digital.library.wayne.edu:8080/oaiprovider/
ListIdentifiers: http://digital.library.wayne.edu:8080/oaiprovider/?verb=ListIdentifiers&metadataPrefix=oai_dc
'''

@manageOAI.route('/manageOAI', methods=['POST', 'GET'])
def index():	
	
	return render_template("manageOAI_index.html")



def manageOAI_genItemID_worker(job_package):

	# get PID
	PID = job_package['PID']		
	obj_ohandle = fedora_handle.get_object(PID)	

	# generate OAI identifier
	OAI_identifier = "oai:digital.library.wayne.edu:{PID}".format(PID=PID)	
	
	print obj_ohandle.add_relationship("http://www.openarchives.org/OAI/2.0/itemID", OAI_identifier)
	



	
























