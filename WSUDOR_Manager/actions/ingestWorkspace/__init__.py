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
import xmltodict

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
	columns.append(ColumnDT('DMDID'))
	columns.append(ColumnDT('ingested'))
	columns.append(ColumnDT('repository'))

	# defining the initial query depending on your purpose
	query = db.session.query(models.ingest_workspace_object).filter(models.ingest_workspace_object.job_id == job_id)

	# instantiating a DataTable for the query and table needed
	rowTable = DataTables(request.args, models.ingest_workspace_object, query, columns)

	# returns what is needed by DataTable
	return jsonify(rowTable.output_result())


# job delete
@ingestWorkspace.route('/ingestWorkspace/job/<job_id>/delete', methods=['POST', 'GET'])
def deleteJob(job_id):

	j = models.ingest_workspace_job.query.filter_by(id=job_id).first()
	db.session.delete(j)
	db.session.commit()

	return redirect('/tasks/ingestWorkspace')



# job edit / view
@ingestWorkspace.route('/ingestWorkspace/createJob', methods=['POST', 'GET'])
def createJob():

	# render
	return render_template("createJob.html")


@celery.task(name="createJob_factory")
def createJob_factory(job_package):
	
	print "FIRING createJob_factory"

	# get form data
	form_data = job_package['form_data']	

	# set new task_name, for the worker below
	job_package['custom_task_name'] = 'createJob_worker'	

	# get ingest metadata
	if 'upload_data' in job_package:		
		ingest_metadata = job_package['upload_data']
	elif form_data['pasted_metadata'] != '':
		ingest_metadata = form_data['pasted_metadata'] 
	
	# initiate ingest job instance with name
	j = models.ingest_workspace_job(form_data['collection_identifier'])

	# add python bag code
	j.bag_creation_class = form_data['pasted_bag_class']

	# add metadata
	j.ingest_metadata = ingest_metadata

	# bag creation class
	j.bag_creation_class = form_data['pasted_bag_class']

	# set final ingest job values, and commit, add job number to job_package
	j._commit()
	job_package['job_id'] = j.id

	# for each section of METS, break into chunks
	XMLroot = etree.fromstring(ingest_metadata)
	# grab stucture map
	sm = XMLroot.find('{http://www.loc.gov/METS/}structMap')
	sm_div1 = sm.find('{http://www.loc.gov/METS/}div')
	# iterate through
	sm_parts = sm_div1.getchildren()

	# pop METS ingest from job_package	
	if 'upload_data' in job_package:
		job_package['upload_data'] = ''
	elif 'pasted_metadata' in form_data:
		job_package['form_data']['pasted_metadata'] = ''

	# update job info (need length from above)
	redisHandles.r_job_handle.set("job_%s_est_count" % (job_package['job_num']), len(sm_parts))

	# insert into MySQL as ingest_workspace_object rows
	step = 1
	for sm_part in sm_parts:

		print "Creating ingest_workspace_object row %s / %s" % (step, len(sm_parts))
		job_package['step'] = step
		
		# get DMDID
		job_package['DMDID'] = sm_part.attrib['DMDID']
		job_package['object_title'] = sm_part.attrib['LABEL']
		
		print "StructMap part ID: %s" % job_package['DMDID']

		# store structMap section as python dictionary
		sm_dict = xmltodict.parse(etree.tostring(sm_part))
		job_package['struct_map'] = json.dumps(sm_dict)

		# grab descriptive mets:dmdSec
		dmd_handle = XMLroot.xpath("//mets:dmdSec[@ID='%s']" % (sm_part.attrib['DMDID']), namespaces={'mets':'http://www.loc.gov/METS/'})[0]
		# grab MODS record and write to temp file		
		MODS_elem = dmd_handle.find('{http://www.loc.gov/METS/}mdWrap[@MDTYPE="MODS"]/{http://www.loc.gov/METS/}xmlData/{http://www.loc.gov/mods/v3}mods')
		temp_filename = "/tmp/Ouroboros/"+str(uuid.uuid4())+".xml"
		fhand = open(temp_filename,'w')
		fhand.write(etree.tostring(MODS_elem))
		fhand.close()		
		job_package['MODS_temp_filename'] = temp_filename

		# fire task via custom_loop_taskWrapper			
		result = actions.actions.custom_loop_taskWrapper.delay(job_package)
		task_id = result.id

		# Set handle in Redis
		redisHandles.r_job_handle.set("%s" % (task_id), "FIRED,%s" % (job_package['DMDID']))
			
		# update incrementer for total assigned
		jobs.jobUpdateAssignedCount(job_package['job_num'])

		# bump step
		step += 1

	print "Finished entering rows"


@celery.task(name="createJob_worker")
def createJob_worker(job_package):

	print job_package.keys()
	print "Adding ingest_workspace_object for %s / %s" % (job_package['DMDID'],job_package['object_title'])

	# open instance of job
	j = models.ingest_workspace_job.query.filter_by(id=job_package['job_id']).first()

	# instatitate object instance
	o = models.ingest_workspace_object(j, object_title=job_package['object_title'], DMDID=job_package['DMDID'])

	# fill out object row with information from job_package

	# structMap
	o.struct_map = job_package['struct_map']

	# MODS file
	with open(job_package['MODS_temp_filename'], 'r') as fhand:
		o.MODS = fhand.read()

	# add and commit(for now)
	return o._commit()






















