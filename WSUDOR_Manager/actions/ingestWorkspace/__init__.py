# Ingest WorkSpace

# celery
from WSUDOR_Manager import celery, utilities, fedoraHandles

# handles
from WSUDOR_Manager.forms import RDF_edit
from WSUDOR_Manager.solrHandles import solr_handle
from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager import redisHandles, jobs, models, db, forms, models, roles, logging
import WSUDOR_Manager.actions as actions
import WSUDOR_ContentTypes
try:
	import ouroboros_assets
except:
	logging.debug("could not load git submodule 'ouroboros_assets'")
import localConfig

from flask import Blueprint, render_template, abort, request, redirect, session, jsonify, Response

#python modules
from lxml import etree
import re
import json
import os
import tarfile
import uuid
from string import upper
import xmltodict
import requests
import time
import traceback
import subprocess

# sql or
from sqlalchemy import or_

# eulfedora
import eulfedora

# import bagit
import bagit

# flask-SQLalchemy-datatables
from datatables import ColumnDT, DataTables

# mets-reader-writer (metsrw)
import metsrw

# create blueprint
ingestWorkspace = Blueprint('ingestWorkspace', __name__, template_folder='templates', static_folder="static")


#################################################################################
# Routes
#################################################################################

# main view
@ingestWorkspace.route('/ingestWorkspace', methods=['POST', 'GET'])
@roles.auth(['admin','metadata'])
def index():

	# get all jobs
	ijs = models.ingest_workspace_job.query.all()

	return render_template("ingestWorkspace.html", ijs=ijs)


# job edit / view
@ingestWorkspace.route('/ingestWorkspace/job/<job_id>', methods=['POST', 'GET'])
@roles.auth(['admin','metadata'])
def job(job_id):

	# get handle
	j = models.ingest_workspace_job.query.filter_by(id=job_id).first()


	'''
	Two things happen here:
		1) filters are set in session so that AJAX based datatables will pick them up
		2) ingest_id's of query are stored temporarily for filter based celery job
	'''

	# SET SESSIONS VARS
	# set session filters if present
	logging.debug("checking for filters...")
	logging.debug(request.args)

	# row range
	if "row_range" in request.args:
		try:
			row_s,row_e = request.args['row_range'].split("-")
			session['row_s'] = row_s
			session['row_e'] = row_e
		except:
			logging.debug("range malformed, cleaning session")
			utilities.sessionVarClean(session,'row_s')
			utilities.sessionVarClean(session,'row_e')

	# ingested status
	if "ingested" in request.args and request.args['ingested'] != '':
		session['ingested'] = request.args['ingested']
	else:
		utilities.sessionVarClean(session,'ingested')

	# bag created
	if 'bag_path' in request.args and request.args['bag_path'] == "True":
		session['bag_path'] = True
	elif 'bag_path' in request.args and request.args['bag_path'] == "False":
		session['bag_path'] = False
	else:
		utilities.sessionVarClean(session,'bag_path')

	# aem enriched
	if 'aem_enriched' in request.args and request.args['aem_enriched'] == "True":
		session['aem_enriched'] = True
	elif 'aem_enriched' in request.args and request.args['aem_enriched'] == "False":
		session['aem_enriched'] = False
	else:
		utilities.sessionVarClean(session,'aem_enriched')

	# SET SESSIONS VARS
	logging.debug("filtered rows stored in Redis")
	current_row_set = currentRowsSet(job_id,session)
	redisHandles.r_catchall.set('%s_crows_%s' % (session['username'],job_id),json.dumps(list(current_row_set)))

	# render
	return render_template("ingestJob.html", j=j, localConfig=localConfig, ouroboros_assets=ouroboros_assets)


# job delete
@ingestWorkspace.route('/ingestWorkspace/job/<job_id>/delete', methods=['POST', 'GET'])
@roles.auth(['admin','metadata'])
def deleteJob(job_id):

	'''
	Consider removing directory as well...
	'''

	# clean job
	logging.debug("removing job")
	j = models.ingest_workspace_job.query.filter_by(id=job_id).first()
	j._delete()

	# clean object
	logging.debug("removing associated objects with job")
	jos = models.ingest_workspace_object.query.filter_by(job_id=job_id)
	for o in jos:		
		o._delete()
	db.session.commit()

	# remove working directory
	logging.debug("removing ingest_jobs directory")
	os.system('rm -r /home/ouroboros/ingest_jobs/ingest_job_%s' % job_id)

	return redirect('/%s/tasks/ingestWorkspace' % localConfig.APP_PREFIX)



# job edit / view
@ingestWorkspace.route('/ingestWorkspace/createJob', methods=['POST', 'GET'])
@roles.auth(['admin','metadata'])
def createJob():

	# render
	return render_template("createJob.html")



# job edit / view
@ingestWorkspace.route('/ingestWorkspace/objectDetails/<job_id>/<ingest_id>', methods=['POST', 'GET'])
@roles.auth(['admin','metadata'])
def objectDetails(job_id,ingest_id):

	'''
	Render out metadata components for an object for viewing and debugging
	'''	

	# get object handle from DB
	o = models.ingest_workspace_object.query.filter_by(job_id=job_id,ingest_id=ingest_id).first()

	# parse objMeta
	if o.objMeta is not None:
		objMeta = json.loads(o.objMeta)
	else:
		objMeta = None
	
	# attempt directory listing of bag_path
	if o.bag_path != None:
		bag_tree = subprocess.check_output(['tree',o.bag_path])
		bag_tree = bag_tree.decode('utf-8')
	else:
		bag_tree = False	

	# render
	return render_template("objectDetails.html", o=o, objMeta=objMeta, bag_tree=bag_tree)


# row objMeta
@ingestWorkspace.route('/ingestWorkspace/objectDetails/<job_id>/<ingest_id>/objMeta.json', methods=['POST', 'GET'])
@roles.auth(['admin','metadata'])
def objectDetails_objMeta(job_id, ingest_id):

	# get object handle from DB
	o = models.ingest_workspace_object.query.filter_by(job_id=job_id,ingest_id=ingest_id).first()
	return jsonify(json.loads(o.objMeta))



# job edit / view
@ingestWorkspace.route('/ingestWorkspace/job/<job_id>/viewMETS', methods=['POST', 'GET'])
@roles.auth(['admin','metadata'])
def viewMETS(job_id):

	# get handle
	j = models.ingest_workspace_job.query.filter_by(id=job_id).first()

	return Response(j.ingest_metadata, mimetype='text/xml')


# job edit / view
@ingestWorkspace.route('/ingestWorkspace/job/<job_id>/viewEnrichedMETS', methods=['POST', 'GET'])
@roles.auth(['admin','metadata'])
def viewEnrichedMETS(job_id):

	# get handle
	j = models.ingest_workspace_job.query.filter_by(id=job_id).first()

	return Response(j.enrichment_metadata, mimetype='text/xml')


# object row delete
@ingestWorkspace.route('/ingestWorkspace/object/delete/<job_id>/<ingest_id>', methods=['POST', 'GET'])
@roles.auth(['admin','metadata'])
def deleteObject(job_id,ingest_id):


	# clean job
	logging.debug("removing object")
	j = models.ingest_workspace_job.query.filter_by(id=job_id).first()
	o = models.ingest_workspace_object.query.filter_by(job=j, ingest_id=ingest_id).first()
	o._delete()
	db.session.commit()

	# remove working directory
	logging.debug("removing ingest_jobs directory")
	os.system('rm -r /home/ouroboros/ingest_jobs/ingest_job_%s' % job_id)

	return redirect('/%s/tasks/ingestWorkspace/job/%s' % (localConfig.APP_PREFIX, job_id))


# pids from job
@ingestWorkspace.route('/ingestWorkspace/job/<job_id>/job_pids/<output_type>', methods=['POST', 'GET'])
@roles.auth(['admin','metadata'])
def job_pids(job_id, output_type):

	# get handle
	j = models.ingest_workspace_job.query.filter_by(id=job_id).first()

	# get objects
	objs = models.ingest_workspace_object.query.filter_by(job=j)

	if output_type == 'solr_search_terms':
		return " OR ".join(["'%s'" % obj.pid for obj in objs])

	if output_type == 'python_list':
		return ",".join(["'%s'" % obj.pid for obj in objs])



#################################################################################
# Modify Rows from Details
#################################################################################

# object row delete
@ingestWorkspace.route('/ingestWorkspace/object/modify/<job_id>/<ingest_id>/toggle_cover_placeholder', methods=['POST', 'GET'])
@roles.auth(['admin','metadata'])
def toggle_cover_placeholder(job_id,ingest_id):

	# clean job
	logging.debug("removing object")
	j = models.ingest_workspace_job.query.filter_by(id=job_id).first()
	o = models.ingest_workspace_object.query.filter_by(job=j, ingest_id=ingest_id).first()
	
	# get 
	om = models.ObjMeta(**json.loads(o.objMeta))

	# if true, set false
	if 'cover_placeholder' in om.__dict__ and om.cover_placeholder:
		logging.debug("cover placeholder is currently TRUE, setting to FALSE")
		om.cover_placeholder = False
		o.objMeta = om.toJSON()

	elif 'cover_placeholder' not in om.__dict__ or not om.cover_placeholder:
		logging.debug("cover placeholder is currently FALSE, setting to TRUE")
		om.cover_placeholder = True
		o.objMeta = om.toJSON()

	# rewrite on disk
	om.writeToFile(o.bag_path+"/data/objMeta.json")
	
	# commit
	db.session.commit()		

	return redirect('/%s/tasks/ingestWorkspace/objectDetails/%s/%s' % (localConfig.APP_PREFIX, job_id, ingest_id))


#################################################################################
# Datatables Endpoint
#################################################################################

# return json for job
@ingestWorkspace.route('/ingestWorkspace/job/<job_id>.json', methods=['POST', 'GET'])
@roles.auth(['admin','metadata','view'])
def jobjson(job_id):	

	def exists(input):
		if input != None:
			return "<span style='color:green;'>True</span>"
		else:
			return "<span style='color:red;'>False</span>"

	def existsReturnValue(input):
		if input != None and input != "0":
			return "<a target='_blank' href='%s'>live link</a>" % (input)
		else:
			return "<span style='color:red;'>False</span>"

	def boolean(input):		
		if input == "1":
			return "<span style='color:green;'>True</span>"
		else:
			return "<span style='color:red;'>False</span>"

	def bag_validation(input):
		if input == None:
			return "<span style='color:orange;'>None</span>"
		else:
			bag_validation_dict = json.loads(input)
			if bag_validation_dict['verdict']:
				return "<span style='color:green;'>Valid</span>"	
			else:
				return "<span style='color:red;'>Invalid</span>"

	# defining columns
	columns = []	
	columns.append(ColumnDT('ingest_id'))
	columns.append(ColumnDT('object_title'))
	columns.append(ColumnDT('pid'))
	columns.append(ColumnDT('object_type'))
	columns.append(ColumnDT('DMDID'))
	columns.append(ColumnDT('AMDID'))
	columns.append(ColumnDT('file_id'))
	columns.append(ColumnDT('ASpaceID'))	
	columns.append(ColumnDT('struct_map', filter=exists))
	columns.append(ColumnDT('MODS', filter=exists))
	columns.append(ColumnDT('bag_path'))
	columns.append(ColumnDT('bag_validation_dict', filter=bag_validation))
	columns.append(ColumnDT('objMeta', filter=exists))
	columns.append(ColumnDT('ingested', filter=existsReturnValue))
	columns.append(ColumnDT('aem_enriched', filter=boolean))
	columns.append(ColumnDT('repository'))

	# build query
	query = rowQueryBuild(job_id, session)	

	# instantiating a DataTable for the query and table needed
	rowTable = DataTables(request.args, models.ingest_workspace_object, query, columns)


	# returns what is needed by DataTable
	return jsonify(rowTable.output_result())


#################################################################################
# Row Data
#################################################################################
@ingestWorkspace.route('/ingestWorkspace/viewSQLData/<table>/<id>/<column>/<mimetype>', methods=['POST', 'GET'])
@roles.auth(['admin'])
def viewSQLData(table,id,column,mimetype):
	return "Coming soon"


#################################################################################
# Create Ingest Job
#################################################################################


@celery.task(name="createJob_factory")
def createJob_factory(job_package):
	
	logging.debug("FIRING createJob_factory")

	# get form data
	form_data = job_package['form_data']	

	# set new task_name, for the worker below
	job_package['custom_task_name'] = 'createJob_worker'	

	# get ingest metadata
	with open(job_package['upload_data'],'r') as fhand:
		ingest_metadata = fhand.read()
	
	# initiate ingest job instance with name
	j = models.ingest_workspace_job(form_data['collection_name'])	

	# add metadata
	j.ingest_metadata = ingest_metadata	

	# set final ingest job values, and commit, add job number to job_package
	j._commit()
	job_package['job_id'] = j.id
	job_package['job_name'] = j.name

	# WSU METS
	if form_data['METS_type'] == 'wsu':
		
		# for each section of METS, break into chunks
		METSroot = etree.fromstring(ingest_metadata)
		ns = METSroot.nsmap
		
		# grab stucture map
		sm = METSroot.find('{http://www.loc.gov/METS/}structMap')
		collection_level_div = sm.find('{http://www.loc.gov/METS/}div')
		
		# new - xpath, all DMDID sections regardless of level
		'''
		Will need to understand parent moving forward (might be good to include anyhow)
		'''
		sm_parts = collection_level_div.xpath('.//mets:div[@DMDID]', namespaces=ns)
		sm_index = { element.attrib['DMDID']:element for element in sm_parts }

		# get dmd parts
		dmd_parts = [element for element in METSroot.findall('{http://www.loc.gov/METS/}dmdSec')]
		dmd_index = { element.attrib['ID']:element for element in dmd_parts }

		# fire 
		createJob_WSU_METS(form_data, job_package, METSroot, sm, collection_level_div, sm_parts, sm_index, dmd_index, j)

	# Archivematica based METS
	if form_data['METS_type'] == 'archivematica':
		metsrw_handle = metsrw.METSDocument.fromstring(ingest_metadata)
		createJob_Archivematica_METS(form_data,job_package,metsrw_handle,j)


def createJob_WSU_METS(form_data, job_package, METSroot, sm, collection_level_div, sm_parts, sm_index, dmd_index, j):
	
	# determine collection identifier
	try:
		# attempt to grab DMD id
		j.collection_identifier = collection_level_div.attrib['DMDID']
		j._commit()
		METS_collection = True
	except:
		METS_collection = False
		if form_data['collection_identifier'] != '':
			j.collection_identifier = form_data['collection_identifier'].split(":")[-1].split("collection")[-1]
		else:
			j.collection_identifier = "Undefined"
		j._commit()

	# set collection identifier in job_package
	job_package['collection_identifier'] = j.collection_identifier
	
	# add collection object to front of list
	if METS_collection:
		sm_parts.insert(0,collection_level_div)

	# update job info (need length from above)
	redisHandles.r_job_handle.set("job_%s_est_count" % (job_package['job_num']), len(sm_parts))

	# insert into MySQL as ingest_workspace_object rows
	step = 1
	
	# iterate through and add components
	for i, sm_part in enumerate(sm_parts):
		
		logging.debug("Creating ingest_workspace_object row %s / %s" % (step, len(sm_parts)))
		job_package['step'] = step

		# set internal id (used for selecting when making bags and ingesting)
		job_package['ingest_id'] = step

		# set type
		if METS_collection and i == 0:
			job_package['object_type'] = "collection"
		else:
			job_package['object_type'] = "component"

		# attempt to fire worker
		try:
			
			# get DMDID
			job_package['DMDID'] = sm_part.attrib['DMDID']

			# set empty AMDID and file_id
			job_package['AMDID'], job_package['file_id'] = [None, None]

			# attempt to get label
			if "LABEL" in sm_part.attrib and sm_part.attrib['LABEL'] != '':
				job_package['object_title'] = sm_part.attrib['LABEL']
			else:
				logging.debug("label not found for %s, using DMDID" % sm_part.attrib['DMDID'])
				job_package['object_title'] = sm_part.attrib['DMDID']

			# logging.debug("StructMap part ID: %s" % job_package['DMDID'])

			# store structMap section as python dictionary
			sm_dict = xmltodict.parse(etree.tostring(sm_part))
			job_package['struct_map'] = json.dumps(sm_dict)

			# grab descriptive mets:dmdSec

			# Use DMD index
			dmd_handle = dmd_index[sm_part.attrib['DMDID']]
			# grab MODS record and write to temp file		
			MODS_elem = dmd_handle.find('{http://www.loc.gov/METS/}mdWrap[@MDTYPE="MODS"]/{http://www.loc.gov/METS/}xmlData/{http://www.loc.gov/mods/v3}mods')
			
			temp_filename = "/tmp/Ouroboros/"+str(uuid.uuid4())+".xml"
			fhand = open(temp_filename,'w')
			fhand.write(etree.tostring(MODS_elem))
			fhand.close()		
			job_package['MODS_temp_filename'] = temp_filename

			# not storing PREMIS events yet
			job_package['premis_events'] = None

		except:
			logging.debug("ERROR")
			logging.debug(traceback.print_exc())

		# fire task via custom_loop_taskWrapper			
		result = actions.actions.custom_loop_taskWrapper.apply_async(kwargs={'job_package':job_package}, queue=job_package['username'])
		task_id = result.id

		# Set handle in Redis
		redisHandles.r_job_handle.set("%s" % (task_id), "FIRED,%s" % (job_package['DMDID']))
			
		# update incrementer for total assigned
		jobs.jobUpdateAssignedCount(job_package['job_num'])

		# bump step
		step += 1


def createJob_Archivematica_METS(form_data,job_package,metsrw_handle,j):

	# handle collection
	if form_data['collection_identifier'] != '':
		j.collection_identifier = form_data['collection_identifier'].split(":")[-1].split("collection")[-1]
	else:
		j.collection_identifier = "Undefined"
	j._commit()

	# set collection identifier in job_package
	job_package['collection_identifier'] = j.collection_identifier
	
	# parse Archivematica METS
	# mets = metsrw.METSDocument.fromstring(ingest_metadata)
	mets = metsrw_handle

	# grab stucture map
	sm = mets.tree.find('{http://www.loc.gov/METS/}structMap')

	# original files
	# orig_files = [ fs for fs in mets.all_files() if fs.use == 'original' ]
	orig_files = [ fs for fs in mets.all_files() ]

	# update job info (need length from above)
	redisHandles.r_job_handle.set("job_%s_est_count" % (job_package['job_num']), len(orig_files))

	# insert into MySQL as ingest_workspace_object rows
	step = 1
	
	# iterate through and add components
	for i, fs in enumerate(orig_files):
		logging.debug("%s %s" % (i,fs.label))

		logging.debug("Creating ingest_workspace_object row %s / %s" % (step, len(orig_files)))
		job_package['step'] = step

		# set internal id (used for selecting when making bags and ingesting)
		job_package['ingest_id'] = step

		# set type				
		job_package['object_type'] = fs.type

		# get DMDID
		job_package['DMDID'] = None
		job_package['object_title'] = fs.label

		# set dynamic PID (may get updated)
		###############################################################################################
		# set identifier with filename
		pid_suffix = job_package['collection_identifier']+fs.label.replace(".","_")
		pid = "wayne:%s" % (pid_suffix)
		job_package['pid'] = pid
		###############################################################################################

		# set file_id
		job_package['file_id'] = fs.file_id()

		# parse amdSec and PREMIS events
		if len(fs.admids) > 0:
			logging.debug("amdSec ids: %s" % fs.admids)
			job_package['AMDID'] = fs.admids[0]			
			amdSec = mets.tree.xpath("//mets:amdSec[@ID='%s']" % (job_package['AMDID']), namespaces=mets.tree.getroot().nsmap)[0]
			events_list = []
			premis_events = amdSec.getchildren()
			for event in premis_events:
				events_list.append(etree.tostring(event.getchildren()[0].getchildren()[0].getchildren()[0]))
			premis_events_json = json.dumps(events_list)
			job_package['premis_events'] = premis_events_json
		else:
			job_package['AMDID'] = None
			job_package['premis_events'] = None

		
		logging.debug("StructMap part ID: %s" % job_package['DMDID'])

		'''
		It's possible we shouldn't write this entire struct_map to celery job?
		Grab in worker below?
		'''

		# store structMap section as python dictionary
		sm_dict = xmltodict.parse(etree.tostring(fs.serialize_structmap()))
		job_package['struct_map'] = json.dumps(sm_dict)

		# write generic MODS
		# Note: Remove <mods:extension><PID>, as PID is not known at this point.
		raw_MODS = '''
<mods:mods xmlns:mods="http://www.loc.gov/mods/v3" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="3.4" xsi:schemaLocation="http://www.loc.gov/mods/v3 http://www.loc.gov/standards/mods/v3/mods-3-4.xsd">
	<mods:titleInfo>
	<mods:title>%s</mods:title>
	</mods:titleInfo>
	<mods:identifier type="local">%s</mods:identifier>
	<mods:extension>
		<orig_filename>%s</orig_filename>
	</mods:extension>
</mods:mods>
			''' % (fs.label, fs.file_uuid, fs.label)
		temp_filename = "/tmp/Ouroboros/"+str(uuid.uuid4())+".xml"
		fhand = open(temp_filename,'w')
		fhand.write(raw_MODS)
		fhand.close()		
		job_package['MODS_temp_filename'] = temp_filename

		# fire task via custom_loop_taskWrapper			
		result = actions.actions.custom_loop_taskWrapper.apply_async(kwargs={'job_package':job_package}, queue=job_package['username'])
		task_id = result.id

		# Set handle in Redis
		redisHandles.r_job_handle.set("%s" % (task_id), "FIRED,%s" % (job_package['DMDID']))
			
		# update incrementer for total assigned
		jobs.jobUpdateAssignedCount(job_package['job_num'])

		# bump step
		step += 1


@celery.task(name="createJob_worker")
@roles.auth(['admin'], is_celery=True)
def createJob_worker(job_package):

	logging.debug("Adding ingest_workspace_object for %s / %s" % (job_package['DMDID'],job_package['object_title']))

	# MODS file
	if job_package['MODS_temp_filename']:
		with open(job_package['MODS_temp_filename'], 'r') as fhand:
			MODS = fhand.read()
			os.remove(job_package['MODS_temp_filename'])
	else:
		MODS = None

	# determine pid
	if job_package['object_type'] == 'collection':
		id_prefix = 'collection'
	else:
		id_prefix = ''

	# this may or may not be true - bag creation should update this...
	if 'pid' in job_package and job_package['pid'] != None:
		derived_pid = job_package['pid']
	else:
		derived_pid = 'wayne:%s%s' % (id_prefix,job_package['DMDID'])

	# insert with SQLAlchemy Core
	db.session.execute(models.ingest_workspace_object.__table__.insert(), [{
		'job_id': job_package['job_id'],	    
		'object_type': job_package['object_type'],
		'object_title': job_package['object_title'],
		'DMDID': job_package['DMDID'],
		'AMDID': job_package['AMDID'],
		'premis_events': job_package['premis_events'],
		'file_id': job_package['file_id'],
		'pid': derived_pid,
		'ingest_id': job_package['ingest_id'],
		'struct_map': job_package['struct_map'],
		'MODS': MODS
	}])

	db.session.commit()


#################################################################################
# Create Bag 
#################################################################################

@celery.task(name="createBag_factory")
def createBag_factory(job_package):
	
	logging.debug("FIRING createBag_factory")
	
	# DEBUG
	# logging.debug(job_package)

	# get form data
	form_data = job_package['form_data']	

	# set bag dir
	bag_dir = '/home/ouroboros/ingest_jobs/ingest_job_%s' % (form_data['job_id'])
	job_package['bag_dir'] = bag_dir
	if not os.path.exists(bag_dir):
		os.mkdir(bag_dir)

	# set new task_name, for the worker below
	job_package['custom_task_name'] = 'createBag_worker'

	# parse object rows from range (use parseIntSet() above)
	if form_data['object_id_range'].lower() == "all":
		object_rows = set(json.loads(redisHandles.r_catchall.get('%s_crows_%s' % (job_package['username'],form_data['job_id']) )))
	else:
		object_rows = parseIntSet(nputstr=form_data['object_id_range'])

	# update job info (need length from above)
	redisHandles.r_job_handle.set("job_%s_est_count" % (job_package['job_num']), len(object_rows))

	# If file path included, reindex files
	# parse and index files, add to job rows
	if form_data['files_location'] != '':

		# if skip not checked
		if 'binary_index' in form_data and form_data['binary_index'] == 'on':
			
			j = models.ingest_workspace_job.query.filter_by(id=int(form_data['job_id'])).first()
			logging.debug("adding file index for %s" % j.name)
			time.sleep(5)

			logging.debug("updating file index for bags")
			fd = {}
			for root, directories, files in os.walk (form_data['files_location'], followlinks=False):
				for filename in files:
					filePath = os.path.join(root,filename)
					logging.debug("adding %s" % filePath)
					fd[filename] = filePath

			# add to job in MySQL
			j.file_index = json.dumps(fd)
			j._commit()

	# insert into MySQL as ingest_workspace_object rows
	step = 1
	time.sleep(2)
	for row in object_rows:

		logging.debug("Creating bag for ingest_id: %s, count %s / %s" % (row, step, len(object_rows)))
		job_package['step'] = step

		# set row
		job_package['ingest_id'] = row
		job_package['job_id'] = form_data['job_id']
		
		result = actions.actions.custom_loop_taskWrapper.apply_async(kwargs={'job_package':job_package}, queue=job_package['username'])
		task_id = result.id

		# Set handle in Redis
		redisHandles.r_job_handle.set("%s" % (task_id), "FIRED,%s" % (step))
			
		# update incrementer for total assigned
		jobs.jobUpdateAssignedCount(job_package['job_num'])

		# bump step
		step += 1
	


@celery.task(name="createBag_worker")
@roles.auth(['admin'], is_celery=True)
def createBag_worker(job_package):

	logging.debug("FIRING createBag_worker")

	# get form data
	form_data = job_package['form_data']

	# determine if purging old bags
	if 'purge_bags' in form_data and form_data['purge_bags'] == 'on':
		purge_bags = True
	else:
		purge_bags = False

	# get object row
	o = models.ingest_workspace_object.query.filter_by(ingest_id=job_package['ingest_id'],job_id=job_package['job_id']).first()
	logging.debug("Working on: %s" % o.object_title)

	# load bag class
	logging.debug("loading bag class for %s" % form_data['bag_creation_class']	)
	bag_class_handle = getattr(ouroboros_assets.bag_classes, form_data['bag_creation_class'])

	# load collection class (if needed)
	collection_class_handle = getattr(ouroboros_assets.bag_classes, 'collection_object')

	# load MODS as etree element
	try:
		MODS_root = etree.fromstring(o.MODS)	
		ns = MODS_root.nsmap
		MODS_handle = {
			"MODS_element" : MODS_root.xpath('//mods:mods', namespaces=ns)[0],
			"MODS_ns" : ns
		}
	except:
		MODS_handle = False
		logging.debug("could not load MODS as etree element")

	# attempt to pre-load METS with metsrw
	try:
		temp_filename = '/tmp/Ouroboros/%s.xml' % uuid.uuid4()
		with open(temp_filename, 'w') as fhand:
			fhand.write(o.job.ingest_metadata.encode('utf-8'))
		o.metsrw_parsed = metsrw.METSDocument.fromfile(temp_filename)
		os.remove(temp_filename)
	except:
		logging.debug("could not pre-parse METS file with metsrw")

	# if not purging bags, and previous bag_path already found, skip
	if purge_bags == False and o.bag_path != None:
		logging.debug("skipping bag creation for %s / %s, already exists" % (o.object_title,o.DMDID))
		bag_result = False	

	# else, create bags (either overwriting or creating new)
	else:
		# instantiate bag_class_worker from class
		if o.object_type == 'collection':
			logging.debug("firing collection object bag creator")
			class_handle = collection_class_handle
		else:
			class_handle = bag_class_handle

		# NEW - streamlined
		bag_class_worker = class_handle.BagClass(
			object_row = o,
			ObjMeta = models.ObjMeta,
			bag_root_dir = job_package['bag_dir'],
			files_location = form_data['files_location'],			
			purge_bags = purge_bags
		)

		bag_result = bag_class_worker.createBag()

	# finish up with updated values from bag_class_worker

	# write some data back to DB
	if purge_bags == True:
		# remove previously recorded and stored bag
		os.system("rm -r %s" % o.bag_path)

	# sets, or updates, the bag path
	o.bag_path = bag_class_worker.obj_dir

	# validate bag
	obj = WSUDOR_ContentTypes.WSUDOR_Object(o.bag_path,object_type='bag')
	o.bag_validation_dict = json.dumps(obj.validIngestBag())

	# set objMeta
	o.objMeta = bag_class_worker.objMeta_handle.toJSON()

	# set PID
	o.pid = bag_class_worker.pid

	# commit
	bag_class_worker.object_row._commit()
	

	return bag_result	



#################################################################################
# Ingest Bag 
#################################################################################

@celery.task(name="ingestBag_factory")
def ingestBag_factory(job_package):
	
	'''
	offloads to actions/bagIngest.bagIngest_worker()
	'''

	logging.debug("FIRING ingestBag_factory")
	
	# DEBUG
	# logging.debug(job_package)

	# get form data
	form_data = job_package['form_data']

	# set new task_name, for the worker below
	job_package['custom_task_name'] = 'bagIngest_worker'

	# parse object rows from range (use parseIntSet() above)
	if form_data['object_id_range'].lower() == "all":
		object_rows = set(json.loads(redisHandles.r_catchall.get('%s_crows_%s' % (job_package['username'],form_data['job_id']) )))
	else:
		object_rows = parseIntSet(nputstr=form_data['object_id_range'])

	# update job info (need length from above)
	redisHandles.r_job_handle.set("job_%s_est_count" % (job_package['job_num']), len(object_rows))
	
	# insert into MySQL as ingest_workspace_object rows
	step = 1
	time.sleep(.5)
	for row in object_rows:

		logging.debug("Preparing to ingest ingest_id: %s, count %s / %s" % (row, step, len(object_rows)))
		job_package['step'] = step

		# set row
		job_package['ingest_id'] = row
		job_package['job_id'] = form_data['job_id']

		# open row, get currently held bag_dir
		o = models.ingest_workspace_object.query.filter_by(ingest_id=job_package['ingest_id'],job_id=job_package['job_id']).first()
		if o.bag_path != None:
			job_package['bag_dir'] = o.bag_path
		else:
			job_package['bag_dir'] = False

		# check if enriched or permitted to ingest anyway
		if o.aem_enriched or 'ingest_non_enriched' in form_data:
		
			result = actions.actions.custom_loop_taskWrapper.apply_async(kwargs={'job_package':job_package}, queue=job_package['username'])
			task_id = result.id

			# Set handle in Redis
			redisHandles.r_job_handle.set("%s" % (task_id), "FIRED,%s" % (step))
				
			# update incrementer for total assigned
			jobs.jobUpdateAssignedCount(job_package['job_num'])

		else:
			logging.debug("eitiher object not-enriched, or permission not granted to ingest non-enriched")

		# bump step
		step += 1


@celery.task(name="ingestBag_callback")
def ingestBag_callback(job_package):
	
	logging.debug("FIRING ingestBag_callback")

	'''
	This is an opportunity check the status of the ingest.
	'''	

	# open handle
	o = models.ingest_workspace_object.query.filter_by(ingest_id=job_package['ingest_id'],job_id=job_package['job_id']).first()
	logging.debug("Retrieved row: %s / %s" % (o.ingest_id,o.object_title))
	
	# set ingested link
	remote_repo_host = localConfig.REMOTE_REPOSITORIES[job_package['form_data']['dest_repo']]['PUBLIC_ROOT']
	o.ingested = "%s/item/%s" % (remote_repo_host, o.pid)
	# o.ingested = job_package['form_data']['dest_repo']
	return o._commit()


#################################################################################
# Check Object Status
#################################################################################

@celery.task(name="checkObjectStatus_factory")
def checkObjectStatus_factory(job_package):
	
	logging.debug("FIRING checkObjectStatus_factory")

	# get form data
	form_data = job_package['form_data']	

	# set new task_name, for the worker below
	job_package['custom_task_name'] = 'checkObjectStatus_worker'

	# parse object rows from range (use parseIntSet() above)
	logging.debug(form_data['object_id_range'].lower())
	if form_data['object_id_range'].lower() == "all":
		object_rows = set(json.loads(redisHandles.r_catchall.get('%s_crows_%s' % (job_package['username'],form_data['job_id']) )))
	else:
		object_rows = parseIntSet(nputstr=form_data['object_id_range'])

	# update job info (need length from above)
	redisHandles.r_job_handle.set("job_%s_est_count" % (job_package['job_num']), len(object_rows))

	# insert into MySQL as ingest_workspace_object rows
	step = 1
	time.sleep(2)
	for row in object_rows:

		logging.debug("Preparing to check object ingest_id: %s, count %s / %s" % (row, step, len(object_rows)))
		job_package['step'] = step

		# set row
		job_package['ingest_id'] = row
		job_package['job_id'] = form_data['job_id']

		result = actions.actions.custom_loop_taskWrapper.apply_async(kwargs={'job_package':job_package}, queue=job_package['username'])
		task_id = result.id

		# Set handle in Redis
		redisHandles.r_job_handle.set("%s" % (task_id), "FIRED,%s" % (step))
			
		# update incrementer for total assigned
		jobs.jobUpdateAssignedCount(job_package['job_num'])

		# bump step
		step += 1
	


@celery.task(name="checkObjectStatus_worker")
@roles.auth(['admin'], is_celery=True)
def checkObjectStatus_worker(job_package):

	'''
	Consider optimizing with SQLAlchemy Core...
	e.g.
	db.session.execute(models.ingest_workspace_object.__table__.insert(), [{
		'job_id': job_package['job_id'],	    
		'object_type': job_package['object_type'],
		'ingest_id': job_package['ingest_id'],
		'struct_map': job_package['struct_map'],
		'MODS': MODS
	}])
	'''

	logging.debug("FIRING checkObjectStatus_worker")

	# get form data
	form_data = job_package['form_data']

	# get object row
	o = models.ingest_workspace_object.query.filter_by(ingest_id=job_package['ingest_id'],job_id=job_package['job_id']).first()
	logging.debug("Checking status of: %s" % o.object_title)

	# assume False commit
	to_commit = False

	# bag path
	if 'check_bag_path' in form_data and form_data['check_bag_path'] == 'on':
		logging.debug("checking bag path: %s" % o.bag_path)
		if o.bag_path != None and os.path.exists(o.bag_path):
			logging.debug("bag_path found.")
		else:
			o.bag_path = None
			to_commit = True

	
	# repo status
	if 'check_repo' in form_data and form_data['check_repo'] == 'on':
		logging.debug("checking existence in repository against %s" % form_data['dest_repo'])
		
		# get fedora handle
		if form_data['dest_repo'] == 'local':
			dest_repo = fedora_handle
		else:
			dest_repo = fedoraHandles.remoteRepo(form_data['dest_repo'])

		# check status
		check_result = dest_repo.get_object(o.pid).exists
		logging.debug("existence check: %s" % check_result)

		# clean status if not found
		if check_result:
			if o.ingested != form_data['dest_repo']:
				o.ingested = form_data['dest_repo']
				to_commit = True
		# clean status if not found
		else:			
			o.ingested = None
			to_commit = True

	# commit if changes made to row
	if to_commit:
		o._commit()


	return job_package

	
#################################################################################
# Enrich Archivematica Metadata
#################################################################################

@celery.task(name="aem_factory")
def aem_factory(job_package):

	logging.debug("FIRING aem_factory")

	# get form data
	form_data = job_package['form_data']

	# set new task_name, for the worker below
	job_package['custom_task_name'] = 'aem_worker'
	job_package['job_id'] = form_data['job_id']

	# get enrichment metadata
	with open(job_package['upload_data'],'r') as fhand:
		enrichment_metadata = fhand.read()
	
	# grab job
	j = models.ingest_workspace_job.query.filter_by(id=job_package['job_id']).first()

	# determine highest ingest_id
	o = models.ingest_workspace_object.query.filter_by(job=j).order_by('ingest_id desc').first()
	high_ingest_id = o.ingest_id

	# add enrichment metadata
	logging.debug("setting new enrichment metadata")
	j.enrichment_metadata = enrichment_metadata
	db.session.commit()

	# for each section of METS, break into chunks
	METSroot = etree.fromstring(j.enrichment_metadata.encode('utf-8'))
	ns = METSroot.nsmap
	
	# grab stucture map
	sm = METSroot.find('{http://www.loc.gov/METS/}structMap')
	collection_level_div = sm.find('{http://www.loc.gov/METS/}div')
	
	# new - xpath, all DMDID sections regardless of level
	sm_parts = collection_level_div.xpath('.//mets:div[@DMDID]', namespaces=ns)
	sm_index = { element.attrib['DMDID']:element for element in sm_parts }

	# reinsert collection level div
	sm_parts.insert(0,collection_level_div)

	# get dmd parts
	dmd_parts = [element for element in METSroot.findall('{http://www.loc.gov/METS/}dmdSec')]
	dmd_index = { element.attrib['ID']:element for element in dmd_parts }
	logging.debug(dmd_index)

	# update job info (need length from above)
	redisHandles.r_job_handle.set("job_%s_est_count" % (job_package['job_num']), len(sm_parts))

	# insert into MySQL as ingest_workspace_object rows
	step = 1
	
	# iterate through and add components
	for i, sm_part in enumerate(sm_parts):
		
		logging.debug("Enriching struct_map div %s / %s" % (step, len(sm_parts)))
		job_package['step'] = step

		# try:

		# include Struct Map and DMD section in job package

		# get DMDID
		job_package['DMDID'] = sm_part.attrib['DMDID']

		# set ingest_id as highest ingest_id + step
		job_package['ingest_id'] = high_ingest_id + step

		# set parent type and DMDID, to determine if hasParent relationship is needed		
		sm_parent = sm_part.getparent()
		job_package['sm_parent'] = dict(sm_parent.attrib)

		# attempt to get label
		if "LABEL" in sm_part.attrib and sm_part.attrib['LABEL'] != '':
			job_package['object_title'] = sm_part.attrib['LABEL']
		else:
			logging.debug("label not found for %s, using DMDID" % sm_part.attrib['DMDID'])
			job_package['object_title'] = sm_part.attrib['DMDID']

		# store structMap section as python dictionary
		sm_dict = xmltodict.parse(etree.tostring(sm_part))
		job_package['struct_map'] = json.dumps(sm_dict)

		# Use DMD index
		dmd_handle = dmd_index[sm_part.attrib['DMDID']]
		# grab MODS record and write to temp file		
		MODS_elem = dmd_handle.find('{http://www.loc.gov/METS/}mdWrap[@MDTYPE="MODS"]/{http://www.loc.gov/METS/}xmlData/{http://www.loc.gov/mods/v3}mods')
		temp_filename = "/tmp/Ouroboros/"+str(uuid.uuid4())+".xml"
		fhand = open(temp_filename,'w')
		fhand.write(etree.tostring(MODS_elem))
		fhand.close()		
		job_package['MODS_temp_filename'] = temp_filename

		# fire task via custom_loop_taskWrapper			
		result = actions.actions.custom_loop_taskWrapper.apply_async(kwargs={'job_package':job_package}, queue=job_package['username'])
		task_id = result.id

		# Set handle in Redis
		redisHandles.r_job_handle.set("%s" % (task_id), "FIRED")
			
		# update incrementer for total assigned
		jobs.jobUpdateAssignedCount(job_package['job_num'])

		# except:

		# 	logging.debug("##############################################")
		# 	logging.debug("an error was had enriching %s" % etree.tostring(sm_part))

		# bump step
		step += 1



@celery.task(name="aem_worker")
@roles.auth(['admin'], is_celery=True)
def aem_worker(job_package):

	# DEBUG
	logging.debug("This represents the intellectual parent as provided by AEM METS: %s" % job_package['sm_parent'])

	# grab job
	j = models.ingest_workspace_job.query.filter_by(id=job_package['job_id']).first()

	intellectual_objects = [
		'series',
		'collection'		
	]

	# get sm_part type
	sm_part = json.loads(job_package['struct_map'])
	sm_part_type = sm_part['mets:div']['@TYPE']

	# MODS file
	if job_package['MODS_temp_filename']:
		with open(job_package['MODS_temp_filename'], 'r') as fhand:
			MODS = fhand.read()
			os.remove(job_package['MODS_temp_filename'])
	else:
		MODS = None

	# attempt to read dmdSec for ASpaceID
	if MODS:
		mods_handle = etree.fromstring(MODS)
		ns = mods_handle.nsmap		
		ASpaceID_elem = mods_handle.find('{http://www.loc.gov/mods/v3}extension/ASpaceID')
		if ASpaceID_elem is not None:
			ASpaceID = ASpaceID_elem.text
		else:
			ASpaceID = None
	else:
		ASpaceID = None

	# intellectual object
	if sm_part_type in intellectual_objects:
		logging.debug("creating new object for %s / %s" % (job_package['DMDID'],job_package['object_title']))

		# check of Intellectual object already created, if so, delete
		derived_pid = 'wayne:%s%s' % (j.collection_identifier, job_package['DMDID'].split("aem_prefix_")[-1])
		'''
		mets:dmdSec IDs cannot start with an integer
		'''
		o = models.ingest_workspace_object.query.filter_by(job=j,pid=derived_pid).first()

		if o:
			o._delete()
			db.session.commit()

		# insert with SQLAlchemy Core
		logging.debug("inserting into DB")
		db.session.execute(models.ingest_workspace_object.__table__.insert(), [{
			'job_id': job_package['job_id'],	    
			'object_type': "Intellectual",
			'object_title': job_package['object_title'],
			'DMDID': job_package['DMDID'],
			'ASpaceID': ASpaceID,
			'pid': derived_pid,
			'ingest_id': job_package['ingest_id'],
			'struct_map': job_package['struct_map'],
			'MODS': MODS,
			'aem_enriched': True
		}])

	# update file-like object
	else:
		logging.debug("updating descriptive information for %s / %s" % (job_package['DMDID'], job_package['object_title']))

		# grab row
		if sm_part_type == 'document':
			logging.debug("detected document type")
			o = models.ingest_workspace_object.query.filter_by(job=j, file_id=job_package['DMDID']).first()			

		if sm_part_type == 'file':
			logging.debug("detected intellectual file type")
			derived_pid = 'wayne:%s%s' % (j.collection_identifier, job_package['DMDID'].split("aem_prefix_")[-1].replace(".","_"))
			logging.debug("derived pid: %s" % derived_pid)
			o = models.ingest_workspace_object.query.filter_by(job=j, pid=derived_pid).first()

		if o:

			# update title
			o.object_title = job_package['object_title']

			# update DMDID
			o.DMDID = job_package['DMDID']

			# update ASpaceID
			o.ASpaceID = ASpaceID

			# update MODS
			o.MODS = MODS

			# enriched
			o.aem_enriched = True

		else:

			logging.debug("couldn't find matching PID row in database for %s" % derived_pid)

	# commit db
	db.session.commit()



#################################################################################
# Utilities
#################################################################################

def rowQueryBuild(job_id, session):

	# begin query definition
	query = db.session.query(models.ingest_workspace_object).filter(models.ingest_workspace_object.job_id == job_id)

	# row start
	if "row_s" in session and "row_e" in session:
		logging.debug("adding row range filter")
		query = query.filter(models.ingest_workspace_object.ingest_id >= session['row_s'])
		query = query.filter(models.ingest_workspace_object.ingest_id <= session['row_e'])

	# ingested status
	if 'ingested' in session:
		logging.debug("adding ingest filter")
		if session['ingested'] == "None":
			query = query.filter(or_(models.ingest_workspace_object.ingested == None, models.ingest_workspace_object.ingested == "0" ))
		else:
			query = query.filter(models.ingest_workspace_object.ingested == session['ingested'])

	# bag created
	if 'bag_path' in session:
		logging.debug("adding bag created filter")
		if session['bag_path']:
			query = query.filter(or_(models.ingest_workspace_object.bag_path != None, models.ingest_workspace_object.bag_path != "0" ))
		if not session['bag_path']:
			query = query.filter(or_(models.ingest_workspace_object.bag_path == None, models.ingest_workspace_object.bag_path == "0" ))

	# aem enriched
	if "aem_enriched" in session:
		logging.debug("adding aem enriched filter")
		if session['aem_enriched']:
			logging.debug("filter: enriched")
			query = query.filter(or_(models.ingest_workspace_object.aem_enriched != None, models.ingest_workspace_object.aem_enriched != "0" ))
		if not session['aem_enriched']:
			logging.debug("filter: NOT enriched")
			query = query.filter(or_(models.ingest_workspace_object.aem_enriched == None, models.ingest_workspace_object.aem_enriched == "0" ))

	# return query object
	return query


def currentRowsSet(job_id,session):
	logging.debug('determining all current rows after filter, setting as selection')
	# perform query and add to set
	query = rowQueryBuild(job_id,session)
	selection = set()
	for o in query.all():
		selection.add(int(o.ingest_id))
	# return
	return selection


def parseIntSet(nputstr=""):
	selection = set()
	invalid = set()
	# tokens are comma seperated values
	tokens = [x.strip() for x in nputstr.split(',')]
	for i in tokens:
		if len(i) > 0:
			if i[:1] == "<":
				i = "1-%s"%(i[1:])
		try:
			# typically tokens are plain old integers
			selection.add(int(i))
		except:
			# if not, then it might be a range
			try:
				token = [int(k.strip()) for k in i.split('-')]
				if len(token) > 1:
					token.sort()
					# we have items seperated by a dash
					# try to build a valid range
					first = token[0]
					last = token[len(token)-1]
					for x in range(first, last+1):
						selection.add(x)
			except:
				# not an int and not a range...
				invalid.add(i)
	# Report invalid tokens before returning valid selection
	if len(invalid) > 0:
		logging.debug("Invalid set: %s" % str(invalid))
	return selection


