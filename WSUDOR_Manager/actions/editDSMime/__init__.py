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
from flask import Blueprint, render_template, redirect, abort

from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager import jobs, models, db, utilities, redisHandles, roles, logging

import localConfig

editDSMime = Blueprint('editDSMime', __name__, template_folder='templates', static_folder="static")


@editDSMime.route('/editDSMime/<PIDnum>')
@utilities.objects_needed
@roles.auth(['admin'])
def index(PIDnum):	
	# gen PIDlet
	PIDlet = jobs.genPIDlet(int(PIDnum))
	if PIDlet == False:
		return utilities.applicationError("PIDnum is out of range.")
	PIDlet['pURL'] = "/tasks/editDSMime/"+str(int(PIDnum)-1)
	PIDlet['nURL'] = "/tasks/editDSMime/"+str(int(PIDnum)+1)

	PID = PIDlet['cPID']

	# get datastreams for object
	obj_ohandle = fedora_handle.get_object(PID)
	ds_list = obj_ohandle.ds_list

	return render_template("editDSMime.html", PIDlet=PIDlet, PIDnum=PIDnum, ds_list=ds_list, APP_HOST=localConfig.APP_HOST)


@roles.auth(['admin'], is_celery=True)
def editDSMime_worker(job_package):
	form_data = job_package['form_data']
	logging.debug(form_data)
		
	try:
		# get PID handle, set state, save()
		PID = job_package['PID']
		obj_ohandle = fedora_handle.get_object(PID)

		# update mime/type
		ds_handle = obj_ohandle.getDatastreamObject(form_data['DSID'].encode('utf-8'))
		ds_handle.mimetype = form_data['mimetype'].encode('utf-8')

		# save constructed object
		return ds_handle.save()

	except:
		return "Could not edit Datastream Mime-Type"


