#!/usr/bin/env python
import requests
import json
import sys
import ast
import os
import xml.etree.ElementTree as ET
import urllib, urllib2
import datetime
from lxml import etree
from flask import Blueprint, render_template, redirect, abort, request, session
from flask.ext.login import login_required

import WSUDOR_ContentTypes
from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager.jobs import getSelPIDs
from WSUDOR_Manager import utilities, roles



purgeObject = Blueprint('purgeObject', __name__, template_folder='templates', static_folder="static")


@purgeObject.route('/purgeObject')
@utilities.objects_needed
@login_required
@roles.auth(['admin'])
def index():

	return render_template("purgeObject.html")


@purgeObject.route('/purgeObject/confirm', methods=['POST','GET'])
@login_required
@roles.auth(['admin'])
def confirm():	

	form_data = request.form
	return render_template("purgeConfirm.html")


@roles.auth(['admin'], is_celery=True)
def purgeObject_worker(job_package):	

	form_data = job_package['form_data']
	pid = job_package['PID']

	# get obj_handle
	obj_handle = WSUDOR_ContentTypes.WSUDOR_Object(pid)

	# check object state
	print obj_handle.ohandle.state
	if obj_handle.ohandle.state != "D":
		return "Skipping, object state not 'Deleted (D)'"

	print "purging Constituents if present"
	if getattr(obj_handle, 'purgeConstituents', None):
		obj_handle.purgeConstituents()
	
	# else, purge object from Fedora (object will be pulled via Messenging service)
	result = fedora_handle.purge_object(obj_handle.pid)
	return "%s purge result: %s" % (obj_handle.pid, result)

	# remove from Solr
	solr_handle.delete_by_key(obj_handle.pid)












	



