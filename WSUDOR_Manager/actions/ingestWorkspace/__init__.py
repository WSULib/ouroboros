# utility for Bag Ingest

# celery
from cl.cl import celery

# handles
from WSUDOR_Manager.forms import RDF_edit
from WSUDOR_Manager.solrHandles import solr_handle
from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager import redisHandles, jobs, models, db, forms
import WSUDOR_Manager.actions as actions
import WSUDOR_ContentTypes
import localConfig

from flask import Blueprint, render_template, abort, request, redirect, session, jsonify

#python modules
from lxml import etree
import re
import json
import os
import tarfile
import uuid

# eulfedora
import eulfedora

# import bagit
import bagit

# create blueprint
ingestWorkspace = Blueprint('ingestWorkspace', __name__, template_folder='templates', static_folder="static")


# main view
@ingestWorkspace.route('/ingestWorkspace', methods=['POST', 'GET'])
def index():

	# get all jobs
	ijs = models.ingest_workspace_job.query.all()

	return render_template("ingestWorkspace.html", ijs=ijs)


# job edit / view
@ingestWorkspace.route('/ingestWorkspace/job/<job_id>', methods=['POST', 'GET'])
def job(job_id):

	# get handle
	j = models.ingest_workspace_job.query.filter_by(id=job_id).first()	

	# render
	return render_template("ingestJob.html", j=j, localConfig=localConfig)


# return json for job
@ingestWorkspace.route('/ingestWorkspace/job/<job_id>.json', methods=['POST', 'GET'])
def jobjson(job_id):

	# get handle
	j = models.ingest_workspace_job.query.filter_by(id=job_id).first()

	# objects
	objects = [ o.serialize() for o in j.objects.all() ]

	# return objects in json form
	return jsonify({
		'records':objects,
		'queryRecordCount': len(objects),
  		'totalRecordCount': len(objects)
	})	















