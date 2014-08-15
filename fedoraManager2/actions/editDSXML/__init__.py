# utility for editing datastream XML

# handles
from fedoraManager2.forms import RDF_edit
from fedoraManager2.solrHandles import solr_handle
from fedoraManager2.fedoraHandles import fedora_handle
from fedoraManager2 import jobs, models, db, utilities, redisHandles
from fedoraManager2.forms import batchIngestForm
import fedoraManager2.actions as actions
import localConfig
from flask import Blueprint, render_template, abort, request, redirect, session

#python modules
from lxml import etree
import re

# eulfedora
import eulfedora

# create blueprint
editDSXML = Blueprint('editDSXML', __name__, template_folder='templates', static_folder="static", static_url_path='/static/editDSXML')

# main view
@editDSXML.route('/editDSXML/<PIDnum>', methods=['POST', 'GET'])
@utilities.objects_needed
def index(PIDnum):	

	# gen PIDlet
	PIDlet = jobs.genPIDlet(int(PIDnum))
	if PIDlet == False:
		return utilities.applicationError("PIDnum is out of range.")
	PIDlet['pURL'] = "/tasks/editDSXML/"+str(int(PIDnum)-1)
	PIDlet['nURL'] = "/tasks/editDSXML/"+str(int(PIDnum)+1)	

	# datastream currently hardcoded to MODS
	DS = "MODS"

	session['editDSXML_pid_num'] = PIDnum
	session['editDSXML_PID'] = PIDlet['cPID']
	session['editDSXML_DS'] = DS
	
	return render_template("editDSXML.html", PIDlet=PIDlet, APP_HOST=localConfig.APP_HOST, APP_BASE_URL=localConfig.APP_BASE_URL)

# update handler
@editDSXML.route('/editDSXML/update', methods=['POST', 'GET'])
def update():	
	'''
	New raw XML contained in request.data
	'''
	# get object info	
	PID = session['editDSXML_PID']	
	DS = session['editDSXML_DS']

	# initialized DS object
	obj_ohandle = fedora_handle.get_object(PID)
	newDS = eulfedora.models.DatastreamObject(obj_ohandle, DS, DS, control_group="X")	

	# construct DS object	
	newDS.mimetype = "text/xml"
	# content		
	newDS.content = request.data
	# save constructed object
	print newDS.save()

	# after save, derive DC from MODS
	actions.DCfromMODS.DCfromMODS_single(PID)

	return "{{PID}} Updated.".format(PID=PID)