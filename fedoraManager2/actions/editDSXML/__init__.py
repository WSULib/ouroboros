# utility for editing datastream XML

# handles
from fedoraManager2.forms import RDF_edit
from fedoraManager2.solrHandles import solr_handle
from fedoraManager2.fedoraHandles import fedora_handle
from fedoraManager2 import redisHandles
from fedoraManager2 import jobs
from fedoraManager2 import models
from fedoraManager2 import db
from fedoraManager2.forms import batchIngestForm
import fedoraManager2.actions as actions
from flask import Blueprint, render_template, abort, request, redirect

#python modules
from lxml import etree
import re

# eulfedora
import eulfedora




# create blueprint
editDSXML = Blueprint('editDSXML', __name__, template_folder='templates')


# main view
@editDSXML.route('/editDSXML', methods=['POST', 'GET'])
def index():
	
	return render_template("editDSXML.html")