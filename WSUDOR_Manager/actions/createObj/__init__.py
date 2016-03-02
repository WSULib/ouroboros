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
from flask import Blueprint, render_template, redirect, abort, request
import uuid
import bagit

import WSUDOR_ContentTypes
from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager import utilities

from WSUDOR_Manager.models import ObjMeta


createObj = Blueprint('createObj', __name__, template_folder='templates', static_folder="static")


@createObj.route('/createObj', methods=['GET', 'POST'])
def index():	

	# get content models
	CMs = [  CM.split(":")[-1] for CM in list(fedora_handle.risearch.get_subjects('fedora-rels-ext:hasContentModel','fedora:CM:ContentModel'))]
	CMs.sort()

	# get policies
	policies = [  policy.split(":")[-1] for policy in list(fedora_handle.risearch.get_subjects('fedora-rels-ext:hasContentModel','fedora:CM:Policy'))]
	policies.sort()

	# render
	return render_template("createObj.html", CMs=CMs, policies=policies)



@createObj.route('/createObj/create', methods=['GET', 'POST'])
def createObj_worker():
	
	form_data = request.form
	print form_data

	# instantiate object with quick variables
	known_values = {
		"id":form_data['pid'],
		"identifier":form_data['pid'].split(':')[-1],
		"label":form_data['label'],
		"content_type":"WSUDOR_%s" % (form_data['CM']),
		"policy":"%s" % (form_data['policy'])
	}

	# instantiate ObjMeta object
	om_handle = ObjMeta(**known_values)

	# show relationships
	om_handle.object_relationships = [
		{
			"predicate": "http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/hasSecurityPolicy",
			"object": "info:fedora/%s" % (form_data['policy'])
		},
		{
			"predicate": "http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/hasSecurityPolicy",
			"object": "info:fedora/%s" % (form_data['policy'])
		}	
	]

	# prepare new working dir & recall original
	working_dir = "/tmp/Ouroboros/"+str(uuid.uuid4())
	print "creating working dir at", working_dir
	# create if doesn't exist
	if not os.path.exists(working_dir):
		os.mkdir(working_dir)			
	os.system("mkdir %s/datastreams" % (working_dir))

	# write objMeta
	print "writing:",om_handle.toJSON()
	om_handle.writeToFile('%s/objMeta.json' % (working_dir))

	if 'bagify' in form_data:
		# bagify
		print 'bagifying'
		bag = bagit.make_bag("%s" % (working_dir), {		
			'Object PID' : form_data['pid']
		})

	# ingest
	if "ingest" in form_data:

		# purge if already exists
		if 'purge' in form_data:
			try:
				print "purging object"
				fedora_handle.purge_object(form_data['pid'])
			except:
				print "object not found, skipping purge"

		# bagify
		if 'bagify' not in form_data:
			print 'bagifying'
			bag = bagit.make_bag("%s" % (working_dir), {		
				'Object PID' : form_data['pid']
			})
		
		# open new handle
		bag_handle = WSUDOR_ContentTypes.WSUDOR_GenObject(payload=working_dir, object_type='bag')
		ingest_result = bag_handle.ingestBag()

		# render
		return render_template('createBag_confirm.html',status="result for %s was %s" % (form_data['pid'],ingest_result))

	else:
		return render_template('createBag_confirm.html',status=working_dir)

	


	


