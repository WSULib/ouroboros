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
from flask.ext.login import login_required
import uuid
import bagit
import time
import shutil

import WSUDOR_ContentTypes
from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager import utilities, forms, roles
from WSUDOR_Manager.utilities import mimetypes
from inc import WSUDOR_bagger

from WSUDOR_Manager.models import ObjMeta


createLearningObj = Blueprint('createLearningObj', __name__, template_folder='templates', static_folder="static")


@createLearningObj.route('/learningObj', methods=['GET', 'POST'])
@login_required
@roles.auth(['admin','metadata'])
def index():	

	# get current learning objects to preview
	los = fedora_handle.risearch.sparql_query('select $lo_title $lo_uri from <#ri> where { $lo_uri <http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/learningObjectFor> $lo_target . $lo_uri <http://purl.org/dc/elements/1.1/title> $lo_title . } ORDER BY ASC($lo_title)')
	los_set = set()
	for lo in los:
		los_set.add((lo['lo_title'], lo['lo_uri'].split("/")[-1]))
	los = list(los_set)

	# render
	return render_template("learningObj.html", los=los)


@createLearningObj.route('/learningObj/create/container', methods=['GET', 'POST'])
@login_required
@roles.auth(['admin','metadata'])
def createContainer():	

	# get collections
	sparql_query = "select $collection_title $collection_uri from <#ri> where { $collection_uri <fedora-rels-ext:hasContentModel> <fedora:CM:Collection> . $collection_uri <http://purl.org/dc/elements/1.1/title> $collection_title . } ORDER BY ASC($collection_title)"
	collections = fedora_handle.risearch.sparql_query(sparql_query)

	# render
	return render_template("createLearningObjContainer.html", collections=collections)



@createLearningObj.route('/learningObj/create/container/worker', methods=['GET', 'POST'])
@login_required
@roles.auth(['admin','metadata'])
def createContainer_worker():
	
	form_data = request.form
	print form_data

	unique_identifier = "LearningObject_%s" % str(uuid.uuid4())
	pid = "wayne:"+unique_identifier

	# instantiate object with quick variables
	known_values = {
		"id":pid,
		"identifier":unique_identifier,
		"label":form_data['label'],
		"description":form_data['description'],
		"creator":form_data['creator'],
		"date":form_data['date'],
		"content_type":"WSUDOR_LearningObject", 
		"policy":"info:fedora/wayne:WSUDORSecurity-permit-apia-unrestricted",
	}

	# instantiate ObjMeta object
	om_handle = ObjMeta(**known_values)

	# show relationships
	om_handle.object_relationships = [		
		{
			"predicate": "info:fedora/fedora-system:def/relations-external#isMemberOfCollection",
			"object": form_data['collection']
		},
		{
			"predicate": "http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/hasParent",
			"object": form_data['collection']
		},		
		{
			"predicate": "http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isDiscoverable",
			"object": "info:fedora/True"
		},
		{
			"predicate": "info:fedora/fedora-system:def/relations-external#hasContentModel",
			"object": "info:fedora/CM:LearningObject"
		},
		{
			"predicate": "http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/preferredContentModel",
			"object": "info:fedora/CM:Container"
		},
		{
			"predicate": "http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/hasSecurityPolicy",
			"object": "info:fedora/wayne:WSUDORSecurity-permit-apia-unrestricted"
		}
	]

	# add optional associated objects
	if "associated_objects" in form_data:
		print "writing associated object relationships"
		associated_objects = [obj.strip() for obj in form_data['associated_objects'].split(',')]
		for obj in associated_objects:
			if obj != '':
				om_handle.object_relationships.append({
					"predicate":"http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/learningObjectFor",
					"object": "info:fedora/%s" % obj
				})

	# prepare new working dir & recall original
	working_dir = "/tmp/Ouroboros/"+str(uuid.uuid4())
	print "creating working dir at", working_dir
	# create if doesn't exist
	if not os.path.exists(working_dir):
		os.mkdir(working_dir)			
	os.system("mkdir %s/datastreams" % (working_dir))

	# write custom MODS
	
	# prepare subjects
	subjects = [subject.strip() for subject in form_data['subjects'].split(",")]
	subject_string = ''
	for subject in subjects:
		if subject != '':
			subject_string += '<mods:subject authority="lcsh"><mods:topic>%s</mods:topic></mods:subject>' % subject

	raw_MODS = '''<?xml version="1.0" encoding="utf-8"?>
<mods:mods xmlns:mods="http://www.loc.gov/mods/v3" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="3.4" xsi:schemaLocation="http://www.loc.gov/mods/v3 http://www.loc.gov/standards/mods/v3/mods-3-4.xsd">
  <mods:titleInfo>
	<mods:title>%(label)s</mods:title>
  </mods:titleInfo>
  <mods:abstract>%(description)s</mods:abstract>
  %(subject_string)s
  <mods:name authority="local" type="person">
	<mods:namePart>%(creator)s</mods:namePart>
	<mods:role>
	  <mods:roleTerm authority="marcrelator" type="text">creator</mods:roleTerm>
	</mods:role>
  </mods:name>
  <mods:originInfo>
	<mods:dateIssued encoding="w3cdtf" keyDate="yes">%(date)s</mods:dateIssued>
  </mods:originInfo>
  <mods:identifier type="local">%(identifier)s</mods:identifier>
  <mods:extension>
	<PID>%(id)s</PID>
  </mods:extension>
  <mods:accessCondition type="useAndReproduction">%(rights)s</mods:accessCondition>
</mods:mods>
	''' % {
			'label':om_handle.label,
			'description':om_handle.description,
			'creator':om_handle.creator,
			'date':om_handle.date,
			'id':om_handle.id,
			'identifier':om_handle.identifier,
			'subject_string':subject_string,
			'rights':form_data['rights']
		}
	print raw_MODS
	with open('%s/MODS.xml' % working_dir,'w') as f:
		f.write(raw_MODS)

	# write objMeta
	print "writing:",om_handle.toJSON()
	om_handle.writeToFile('%s/objMeta.json' % (working_dir))

	# bagify
	print 'bagifying'	
	bag = WSUDOR_bagger.make_bag(working_dir, {
		'Object PID' : pid
	})

	# ingest
	# purge if already exists
	if 'purge' in form_data:
		try:
			print "purging object"
			fedora_handle.purge_object(form_data['pid'])
		except:
			print "object not found, skipping purge"

	# open new handle
	bag_handle = WSUDOR_ContentTypes.WSUDOR_Object(payload=working_dir, object_type='bag')
	ingest_result = bag_handle.ingestBag()

	# cleanup
	shutil.rmtree(working_dir)

	# render
	time.sleep(3)
	return redirect('tasks/learningObj/container/%s' % pid)

	

@createLearningObj.route('/learningObj/container/<PID>/create/document', methods=['GET', 'POST'])
@createLearningObj.route('/learningObj/container/<PID>/create/document/', methods=['GET', 'POST'])
@login_required
@roles.auth(['admin','metadata'])
def createDocument(PID):

	# open handle
	obj = WSUDOR_ContentTypes.WSUDOR_Object(PID)

	# get content models
	CMs = [  CM.split(":")[-1] for CM in list(fedora_handle.risearch.get_subjects('fedora-rels-ext:hasContentModel','fedora:CM:ContentModel'))]
	CMs.sort()

	return render_template('createLearningObjDocument.html',obj=obj, form=forms.learningObjectForm(), CMs=CMs)
	


@createLearningObj.route('/learningObj/container/<parent_PID>/create/document/worker', methods=['GET', 'POST'])
@login_required
@roles.auth(['admin','metadata'])
def createDocument_worker(parent_PID):

	form_data = request.form
	print form_data

	# open parent handle
	obj = WSUDOR_ContentTypes.WSUDOR_Object(parent_PID)

	unique_identifier = "LearningObject_File_%s" % str(uuid.uuid4())
	pid = "wayne:"+unique_identifier

	# instantiate object with quick variables
	known_values = {
		"id":pid,
		"identifier":unique_identifier,
		"label":form_data['label'],
		"description":form_data['description'],
		"creator":form_data['creator'],
		"date":form_data['date'],
		"content_type":"WSUDOR_%s" % form_data['CM'], 
		"policy":"info:fedora/wayne:WSUDORSecurity-permit-apia-unrestricted"
	}
	print known_values

	# instantiate ObjMeta object
	om_handle = ObjMeta(**known_values)

	# show relationships
	om_handle.object_relationships = [
		{
			"predicate": "http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/hasParent",
			"object": "info:fedora/%s" % parent_PID
		},
		{
			"predicate": "info:fedora/fedora-system:def/relations-external#isConstituentOf",
			"object": "info:fedora/%s" % parent_PID
		},
		{
			"predicate": "http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isDiscoverable",
			"object": "info:fedora/False"
		},		
		{
			"predicate": "http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/preferredContentModel",
			"object": "info:fedora/CM:%s" % form_data['CM']
		},
		{
			"predicate": "http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/hasSecurityPolicy",
			"object": "info:fedora/wayne:WSUDORSecurity-permit-apia-unrestricted"
		}
	]

	# prepare new working dir & recall original
	working_dir = "/tmp/Ouroboros/"+str(uuid.uuid4())
	print "creating working dir at", working_dir
	# create if doesn't exist
	if not os.path.exists(working_dir):
		os.mkdir(working_dir)			
	os.system("mkdir %s/datastreams" % (working_dir))

	# write custom MODS

	# prepare subjects
	subjects = [subject.strip() for subject in form_data['subjects'].split(",")]
	subject_string = ''
	for subject in subjects:
		if subject != '':
			subject_string += '<mods:subject authority="lcsh"><mods:topic>%s</mods:topic></mods:subject>' % subject

	raw_MODS = '''<?xml version="1.0" encoding="utf-8"?>
<mods:mods xmlns:mods="http://www.loc.gov/mods/v3" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="3.4" xsi:schemaLocation="http://www.loc.gov/mods/v3 http://www.loc.gov/standards/mods/v3/mods-3-4.xsd">
  <mods:titleInfo>
	<mods:title>%(label)s</mods:title>
  </mods:titleInfo>
  <mods:abstract>%(description)s</mods:abstract>
  %(subject_string)s
  <mods:name authority="local" type="person">
	<mods:namePart>%(creator)s</mods:namePart>
	<mods:role>
	  <mods:roleTerm authority="marcrelator" type="text">creator</mods:roleTerm>
	</mods:role>
  </mods:name>
  <mods:originInfo>
	<mods:dateCreated>%(date)s</mods:dateCreated>
  </mods:originInfo>
  <mods:identifier type="local">%(identifier)s</mods:identifier>
  <mods:extension>
	<PID>%(id)s</PID>
  </mods:extension>
  <mods:accessCondition type="useAndReproduction">%(rights)s</mods:accessCondition>
</mods:mods>
	''' % {
			'label':om_handle.label,
			'description':om_handle.description,
			'creator':om_handle.creator,
			'date':om_handle.date,
			'id':om_handle.id,
			'identifier':om_handle.identifier,
			'subject_string':subject_string,
			'rights':form_data['rights']
		}
	print raw_MODS
	with open('%s/MODS.xml' % working_dir,'w') as f:
		f.write(raw_MODS)

	# write datastream
	# Identify datastreams folder
	datastreams_dir = working_dir + "/datastreams"
	target_filename = '%s/%s' % (datastreams_dir,form_data['filename'])

	# retrieve uploaded / pasted / content and write to disk
	if form_data['dataType'] == 'dsLocation':
		file_data = requests.get(form_data['dsLocation'])
		with open(target_filename) as f:
			f.write(file_data.content)

	elif form_data['dataType'] == 'upload':
		# writes to temp file in /tmp/Ouroboros
		if 'upload' in request.files and request.files['upload'].filename != '':
			print "Form provided file, uploading and reading file to variable"
			with open(target_filename,'w') as fhand:
				fhand.write(request.files['upload'].read())

	else:
		print "file could not be found"
		return False

	filename = form_data['filename']
	label = form_data['label']
	order = 1

	# get extension, ds_id
	mimetypes.init()
	ds_id, ext = filename.split(".")

	# create datastream dictionary
	ds_dict = {
		"filename": filename,
		"ds_id": ds_id,
		"mimetype": mimetypes.types_map[".%s" % ext],
		"label": label,
		"internal_relationships": {},
		'order': order
	}

	om_handle.datastreams.append(ds_dict)
	
	om_handle.isRepresentedBy = ds_id

	# write objMeta
	print "writing:",om_handle.toJSON()
	om_handle.writeToFile('%s/objMeta.json' % (working_dir))

	# bagify
	print 'bagifying'	
	bag = WSUDOR_bagger.make_bag(working_dir, {
		'Object PID' : pid
	})

	# ingest
	# purge if already exists
	if 'purge' in form_data:
		try:
			print "purging object"
			fedora_handle.purge_object(form_data['pid'])
		except:
			print "object not found, skipping purge"

	# open new handle
	bag_handle = WSUDOR_ContentTypes.WSUDOR_Object(payload=working_dir, object_type='bag')
	ingest_result = bag_handle.ingestBag()

	# cleanup
	# shutil.rmtree(working_dir)

	# render
	time.sleep(3)
	return redirect('tasks/learningObj/container/%s' % parent_PID)


@createLearningObj.route('/learningObj/container/<PID>', methods=['GET', 'POST'])
@login_required
@roles.auth(['admin','metadata'])
def previewDocument(PID):

	# open handle
	obj = WSUDOR_ContentTypes.WSUDOR_Object(PID)		

	return render_template('previewLearningObj.html', obj=obj)











