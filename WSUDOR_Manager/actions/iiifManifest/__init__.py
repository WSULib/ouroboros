#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
import json
import sys
import ast
import os
import xml.etree.ElementTree as ET
import urllib, urllib2
import datetime
from lxml import etree
import uuid
import StringIO
import tarfile

from flask import Blueprint, render_template, redirect, abort, request, session

import eulfedora

from WSUDOR_Manager.jobs import getSelPIDs, genPIDlet
from WSUDOR_Manager import utilities, redisHandles, roles
import WSUDOR_ContentTypes
import localConfig


iiifManifest = Blueprint('iiifManifest', __name__, template_folder='templates', static_folder="static")

'''
This action is designed to export a given object as a WSUDOR objectBag, an instance of LOC's BagIt standard.
'''


@iiifManifest.route('/iiifManifest')
@utilities.objects_needed
@roles.auth(['admin','metadata','view'])
def index():	

	# get PIDs	
	PIDs = getSelPIDs()
	return render_template("iiifManifest.html")



@iiifManifest.route('/iiifManifest/viewManifests/<PIDnum>')
@utilities.objects_needed
@roles.auth(['admin','metadata','view'])
def viewManifests(PIDnum):	

	# get PIDs	
	PIDs = getSelPIDs()

	# GET CURRENT OBJECTS	
	PIDlet = genPIDlet(int(PIDnum))
	if PIDlet == False:
		return utilities.applicationError("PIDnum is out of range or invalid.  We are is displeased.")
	PIDlet['pURL'] = "/tasks/iiifManifest/viewManifests/"+str(int(PIDnum)-1)
	PIDlet['nURL'] = "/tasks/iiifManifest/viewManifests/"+str(int(PIDnum)+1)
	
	# check Redis for manifest
	r_response = redisHandles.r_iiif.get(PIDlet['cPID'])
	if r_response != None:
		print "Redis hit for manifest."
		json_return = r_response
	else:
		print "Redis miss for manifest."
		json_return = json.dumps({"status":"manifest for %s not found in redis" % PIDlet['cPID']})
	


	return render_template("iiifManifest_view.html",PIDnum=(int(PIDnum)+1),PIDlet=PIDlet, json_return=json.dumps( json.loads(json_return), indent=2), iiif_manifest_prefix=localConfig.IIIF_MANIFEST_PREFIX,APP_HOST=localConfig.APP_HOST )


@roles.auth(['admin','metadata','view'], is_celery=True)
def iiifManifestGenerate_worker(job_package):	 


	obj_handle = WSUDOR_ContentTypes.WSUDOR_Object(job_package['PID'])
	manifest_json = obj_handle.genIIIFManifest()
	if json.loads(manifest_json):		
		return "http://%s/" % (localConfig.APP_HOST)+localConfig.IIIF_MANIFEST_PREFIX+"/"+job_package['PID']
	else:
		return False


