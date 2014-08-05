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

@manageOAI.route('/manageOAI', methods=['POST', 'GET'])
def index():	
	
	return render_template("manageOAI_index.html")


	
























