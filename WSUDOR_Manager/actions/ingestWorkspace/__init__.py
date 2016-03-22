# utility for Bag Ingest

# celery
from cl.cl import celery

# handles
from WSUDOR_Manager.forms import RDF_edit
from WSUDOR_Manager.solrHandles import solr_handle
from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager import redisHandles, jobs, models, db, forms, models
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
from string import upper

# eulfedora
import eulfedora

# import bagit
import bagit

# flask-SQLalchemy-datatables
from datatables import ColumnDT, DataTables

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
	
	# defining columns
	columns = []
	columns.append(ColumnDT('id'))
	columns.append(ColumnDT('object_title'))
	columns.append(ColumnDT('job_id'))    

	# defining the initial query depending on your purpose
	query = db.session.query(models.ingest_workspace_object).filter(models.ingest_workspace_object.job_id == job_id)

	# instantiating a DataTable for the query and table needed
	rowTable = DataTables(request.args, models.ingest_workspace_object, query, columns)

	# returns what is needed by DataTable
	return jsonify(rowTable.output_result())









