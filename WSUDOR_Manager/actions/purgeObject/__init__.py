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

from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager.jobs import getSelPIDs
from WSUDOR_Manager import utilities


purgeObject = Blueprint('purgeObject', __name__, template_folder='templates', static_folder="static")


@purgeObject.route('/purgeObject')
@utilities.objects_needed
def index():

	# get PIDs	
	PIDs = getSelPIDs()
	return render_template("purgeObject.html")


@purgeObject.route('/purgeObject/confirm', methods=['POST','GET'])
def confirm():	

	form_data = request.form
	return render_template("purgeConfirm.html")



def purgeObject_worker(job_package):	

	form_data = job_package['form_data']
	PID = job_package['PID']

	# check object state
	obj_handle = fedora_handle.get_object(PID)
	print obj_handle.state
	if obj_handle.state != "D":
		return "Skipping, object state not 'Deleted (D)'"
	
	# else, purge object from Fedora (object will be pulled via Messenging service)
	result = fedora_handle.purge_object(PID)
	return "%s purge result: %s" % (PID, result)

	# remove from Solr
	solr_handle.delete_by_key(PID)












	



