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
editDSXML = Blueprint('editDSXML', __name__, template_folder='templates', static_folder="static", static_url_path='/static/editDSXML')

'''
UI notes:
	- need to iterate through PIDs for each editor...
'''

# main view
@editDSXML.route('/editDSXML', methods=['POST', 'GET'])
def index():
	
	return render_template("editDSXML.html")


# update handler
@editDSXML.route('/editDSXML/update', methods=['POST', 'GET'])
def update():	
	'''
	New raw XML contained in request.data
	'''

	# get object info
	PID = "wayne:Fake02a" # need to actually get PID...		
	DS = "MODS" # need to get datastream...

	# initialized DS object
	obj_ohandle = fedora_handle.get_object(PID)
	newDS = eulfedora.models.DatastreamObject(obj_ohandle, DS, DS, control_group="X")	

	# construct DS object	
	newDS.mimetype = "text/xml"
	# content		
	newDS.content = request.data
	# save constructed object
	print newDS.save()

	return "Updated."	