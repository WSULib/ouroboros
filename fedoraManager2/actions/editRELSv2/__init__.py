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

	return "Here we go..."
	
























	