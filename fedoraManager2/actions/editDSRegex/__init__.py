# small utility to edit RELS-EXT datastream for objects

# handles
from fedoraManager2.forms import RDF_edit
from fedoraManager2.solrHandles import solr_handle
from fedoraManager2.fedoraHandles import fedora_handle
from fedoraManager2 import models, jobs, db, utilities
from localConfig import *
from flask import Blueprint, render_template, abort, request

#python modules
from lxml import etree
import re
import requests
from requests.auth import HTTPBasicAuth
import json

# eulfedora
import eulfedora

editDSRegex = Blueprint('editDSRegex', __name__, template_folder='templates', static_folder="static")


'''
Improvements:
	- currently hardcoded to MODS, should accept datastream ID
	- currently only works with inline XML, should detect management type and reapply (line 109)
'''


@editDSRegex.route('/editDSRegex', methods=['POST', 'GET'])
@utilities.objects_needed
def index():

	# get PID to examine, if noted
	# if request.args.get("PIDnum") != None:
	if "PIDnum" in request.values:
		PIDnum = int(request.args.get("PIDnum"))		
	else:
		PIDnum = 0	

	# gen PIDlet
	PIDlet = jobs.genPIDlet(PIDnum)	
	if PIDlet == False:		
		return utilities.applicationError("PIDnum is out of range.")
	PIDlet['pURL'] = "/tasks/editDSRegex?PIDnum="+str(PIDnum-1)
	PIDlet['nURL'] = "/tasks/editDSRegex?PIDnum="+str(PIDnum+1)	

	# instantiate forms
	form = RDF_edit()	

	# Raw Datastream via Fedora API
	###############################################################	
	raw_xml_URL = "http://digital.library.wayne.edu/fedora/objects/{PID}/datastreams/MODS/content".format(PID=PIDlet['cPID'])
	raw_xml = requests.get(raw_xml_URL).text.encode("utf-8")
	###############################################################
	
	# return render_template("editDSRegex_index.html",PID=PIDs[PIDnum],PIDnum=PIDnum,len_PIDs=len(PIDs),form=form,raw_xml=raw_xml)
	return render_template("editDSRegex_index.html",PIDlet=PIDlet,PIDnum=PIDnum,form=form,raw_xml=raw_xml)
	



@editDSRegex.route('/editDSRegex/regexConfirm', methods=['POST', 'GET'])
def regexConfirm():
		
	# get PIDs	
	PIDs = jobs.getSelPIDs()			
	form_data = request.form	

	# search / replace
	orig_string = request.form['raw_xml']
	regex_search = request.form['regex_search'].encode('utf-8')
	regex_replace = request.form['regex_replace'].encode('utf-8')
	new_string = re.sub(regex_search,regex_replace,orig_string)	
		
	#debug
	return_package = {
		"orig_string":orig_string,
		"new_string":new_string,
		"regex_search":regex_search,
		"regex_replace":regex_replace		
	}	

	# check diff - if ratio == 100, XML is identical, simply reordered by RDF query
	if orig_string == new_string:
		return_package['string_match'] = True	
	
	return render_template("editDSRegex_regexConfirm.html",return_package=return_package)


def editDSRegex_regex_worker(job_package):		
	
	PID = job_package['PID']		
	obj_ohandle = fedora_handle.get_object(PID)

	# Raw Datastream via Fedora API
	###############################################################	
	raw_xml_URL = "http://digital.library.wayne.edu/fedora/objects/{PID}/datastreams/MODS/content".format(PID=PID)
	raw_xml = requests.get(raw_xml_URL).text.encode("utf-8")	
	###############################################################
	
	# get regex parameters
	form_data = job_package['form_data']	

	# search / replace	
	regex_search = form_data['regex_search'].encode('utf-8')
	regex_replace = form_data['regex_replace'].encode('utf-8')
	new_string = re.sub(regex_search,regex_replace,raw_xml)		

	# similar to addDS functionality	
	DS_handle = eulfedora.models.DatastreamObject(obj_ohandle, "MODS", "MODS", control_group="X")	

	# construct DS object	
	DS_handle.mimetype = "text/xml"

	# content		
	DS_handle.content = new_string	

	# save constructed object
	return DS_handle.save()	
























