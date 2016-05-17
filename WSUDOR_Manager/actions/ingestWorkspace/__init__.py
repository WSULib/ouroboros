# utility for Bag Ingest

# celery
from WSUDOR_Manager import celery, utilities, fedoraHandles

# handles
from WSUDOR_Manager.forms import RDF_edit
from WSUDOR_Manager.solrHandles import solr_handle
from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager import redisHandles, jobs, models, db, forms, models
import WSUDOR_Manager.actions as actions
import WSUDOR_ContentTypes
try:
	import ouroboros_assets
except:
	print "could not load git submodule 'ouroboros_assets'"
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
def index():

	# get all jobs
	ijs = models.ingest_workspace_job.query.all()

	return render_template("ingestWorkspace.html", ijs=ijs)


# job edit / view
@ingestWorkspace.route('/ingestWorkspace/job/<job_id>', methods=['POST', 'GET'])
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
	print "checking for filters..."
	print request.args

	# row range
	if "row_range" in request.args:
		try:
			row_s,row_e = request.args['row_range'].split("-")
			session['row_s'] = row_s
			session['row_e'] = row_e
		except:
			print "range malformed, cleaning session"
			utilities.sessionVarClean(session,'row_s')
			utilities.sessionVarClean(session,'row_e')

	# ingested status
	if "ingested" in request.args and request.args['ingested'] != '':
		session['ingested'] = request.args['ingested']
	else:
		utilities.sessionVarClean(session,'ingested')

	# bag created
	if 'no_bag_path' in request.args and request.args['no_bag_path'] == 'on':
		session['no_bag_path'] = True
	else:
		utilities.sessionVarClean(session,'no_bag_path')

	# SET SESSIONS VARS
	print "filtered rows stored in Redis"
	current_row_set = currentRowsSet(job_id,session)
	redisHandles.r_catchall.set('%s_crows_%s' % (session['username'],job_id),json.dumps(list(current_row_set)))

	# render
	return render_template("ingestJob.html", j=j, localConfig=localConfig, ouroboros_assets=ouroboros_assets)


# job delete
@ingestWorkspace.route('/ingestWorkspace/job/<job_id>/delete', methods=['POST', 'GET'])
def deleteJob(job_id):

	'''
	Consider removing directory as well...
	'''

	# clean job
	print "removing job"
	j = models.ingest_workspace_job.query.filter_by(id=job_id).first()
	j._delete()

	# clean object
	print "removing associated objects with job"
	jos = models.ingest_workspace_object.query.filter_by(job_id=job_id)
	for o in jos:		
		o._delete()
	db.session.commit()

	# remove working directory
	print "removing ingest_jobs directory"
	os.system('rm -r /home/ouroboros/ingest_jobs/ingest_job_%s' % job_id)

	return redirect('/%s/tasks/ingestWorkspace' % localConfig.APP_PREFIX)



# job edit / view
@ingestWorkspace.route('/ingestWorkspace/createJob', methods=['POST', 'GET'])
def createJob():

	# render
	return render_template("createJob.html")



# job edit / view
@ingestWorkspace.route('/ingestWorkspace/objectDetails/<job_id>/<ingest_id>', methods=['POST', 'GET'])
def objectDetails(job_id,ingest_id):

	'''
	Render out metadata components for an object for viewing and debugging
	'''	

	# get object handle from DB
	o = models.ingest_workspace_object.query.filter_by(job_id=job_id,ingest_id=ingest_id).first()
	
	# attempt directory listing of bag_path
	if o.bag_path != None:
		bag_tree = subprocess.check_output(['tree',o.bag_path])
		bag_tree = bag_tree.decode('utf-8')
	else:
		bag_tree = False	

	# render
	return render_template("objectDetails.html",o=o,bag_tree=bag_tree)



# job edit / view
@ingestWorkspace.route('/ingestWorkspace/job/<job_id>/viewMETS', methods=['POST', 'GET'])
def viewMETS(job_id):

	# get handle
	j = models.ingest_workspace_job.query.filter_by(id=job_id).first()

	return Response(j.ingest_metadata, mimetype='text/xml')



#################################################################################
# Datatables Endpoint
#################################################################################

# return json for job
@ingestWorkspace.route('/ingestWorkspace/job/<job_id>.json', methods=['POST', 'GET'])
def jobjson(job_id):	

	def exists(input):
		if input != None:
			return "<span style='color:green;'>True</span>"
		else:
			return "<span style='color:red;'>False</span>"


	def existsReturnValue(input):
		if input != None and input != "0":
			return input
		else:
			return "<span style='color:red;'>False</span>"

	def boolean(input):		
		if input == "1":
			return "<span style='color:green;'>True</span>"
		else:
			return "<span style='color:red;'>False</span>"
	
	# defining columns
	columns = []	
	columns.append(ColumnDT('ingest_id'))
	columns.append(ColumnDT('object_title'))
	columns.append(ColumnDT('pid'))
	columns.append(ColumnDT('object_type'))
	columns.append(ColumnDT('DMDID'))	
	columns.append(ColumnDT('struct_map', filter=exists))
	columns.append(ColumnDT('MODS', filter=exists))
	columns.append(ColumnDT('bag_path'))
	columns.append(ColumnDT('objMeta', filter=exists))
	columns.append(ColumnDT('ingested', filter=existsReturnValue))
	columns.append(ColumnDT('repository'))

	# build query
	query = rowQueryBuild(job_id, session)	

	# instantiating a DataTable for the query and table needed
	rowTable = DataTables(request.args, models.ingest_workspace_object, query, columns)


	# returns what is needed by DataTable
	return jsonify(rowTable.output_result())


#################################################################################
# View SQL row data
#################################################################################
@ingestWorkspace.route('/ingestWorkspace/viewSQLData/<table>/<id>/<column>/<mimetype>', methods=['POST', 'GET'])
def viewSQLData(table,id,column,mimetype):
	return "Coming soon"



#################################################################################
# Create Ingest Job
#################################################################################


def createJob_WSU_METS(form_data,job_package,METSroot,sm,collection_level_div,sm_parts,j):
	
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
			j.collection_identifier = "Loose"
		j._commit()
	
	# add collection object to front of list
	if METS_collection:
		sm_parts.insert(0,collection_level_div)	

	# update job info (need length from above)
	redisHandles.r_job_handle.set("job_%s_est_count" % (job_package['job_num']), len(sm_parts))

	# insert into MySQL as ingest_workspace_object rows
	step = 1
	
	# iterate through and add components
	for i,sm_part in enumerate(sm_parts):
		
		print "Creating ingest_workspace_object row %s / %s" % (step, len(sm_parts))
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

			# attempt to get label
			if "LABEL" in sm_part.attrib and sm_part.attrib['LABEL'] != '':
				job_package['object_title'] = sm_part.attrib['LABEL']
			else:
				print "label not found for %s, using DMDID" % sm_part.attrib['DMDID']
				job_package['object_title'] = sm_part.attrib['DMDID']

			print "StructMap part ID: %s" % job_package['DMDID']

			# store structMap section as python dictionary
			sm_dict = xmltodict.parse(etree.tostring(sm_part))
			job_package['struct_map'] = json.dumps(sm_dict)

			# grab descriptive mets:dmdSec

			# This section can be slow for large files - better way to find element?
			#############################################################################
			dmd_handle = METSroot.find("mets:dmdSec[@ID='%s']" % (sm_part.attrib['DMDID']), namespaces={'mets':'http://www.loc.gov/METS/'})
			# grab MODS record and write to temp file		
			MODS_elem = dmd_handle.find('{http://www.loc.gov/METS/}mdWrap[@MDTYPE="MODS"]/{http://www.loc.gov/METS/}xmlData/{http://www.loc.gov/mods/v3}mods')
			#############################################################################
			
			temp_filename = "/tmp/Ouroboros/"+str(uuid.uuid4())+".xml"
			fhand = open(temp_filename,'w')
			fhand.write(etree.tostring(MODS_elem))
			fhand.close()		
			job_package['MODS_temp_filename'] = temp_filename

		except:
			print "ERROR"
			print traceback.print_exc()

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
		j.collection_identifier = "Loose"
	j._commit()
	
	# parse Archivematica METS
	# mets = metsrw.METSDocument.fromstring(ingest_metadata)
	mets = metsrw_handle
	# print mets.all_files()

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
		print i,fs.label

		print "Creating ingest_workspace_object row %s / %s" % (step, len(orig_files))
		job_package['step'] = step

		# set internal id (used for selecting when making bags and ingesting)
		job_package['ingest_id'] = step

		# set type				
		job_package['object_type'] = fs.type

		# attempt to fire worker
		# try:
			
		# get DMDID
		job_package['DMDID'] = None
		job_package['object_title'] = fs.label
		
		print "StructMap part ID: %s" % job_package['DMDID']

		# store structMap section as python dictionary
		sm_dict = xmltodict.parse(etree.tostring(fs.serialize_structmap()))
		job_package['struct_map'] = json.dumps(sm_dict)

		# write generic MODS
		raw_MODS = '''
<mods:mods xmlns:mods="http://www.loc.gov/mods/v3" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="3.4" xsi:schemaLocation="http://www.loc.gov/mods/v3 http://www.loc.gov/standards/mods/v3/mods-3-4.xsd">
<mods:titleInfo>
<mods:title>%s</mods:title>
</mods:titleInfo>
<mods:identifier type="local">%s</mods:identifier>
<mods:extension>
<PID>wayne:%s</PID>
</mods:extension>
</mods:mods>
			''' % (fs.label, fs.file_uuid, fs.file_uuid)
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


@celery.task(name="createJob_factory")
def createJob_factory(job_package):
	
	print "FIRING createJob_factory"

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
		# grab stucture map
		sm = METSroot.find('{http://www.loc.gov/METS/}structMap')
		collection_level_div = sm.find('{http://www.loc.gov/METS/}div')
		# iterate through, ignoring comments
		sm_parts = [element for element in collection_level_div.getchildren() if type(element) != etree._Comment]
		createJob_WSU_METS(form_data,job_package,METSroot,sm,collection_level_div,sm_parts,j)

	# Archivematica based METS
	if form_data['METS_type'] == 'archivematica':
		metsrw_handle = metsrw.METSDocument.fromstring(ingest_metadata)
		createJob_Archivematica_METS(form_data,job_package,metsrw_handle,j)



@celery.task(name="createJob_worker")
def createJob_worker(job_package):

	print job_package.keys()
	print "Adding ingest_workspace_object for %s / %s" % (job_package['DMDID'],job_package['object_title'])

	# open instance of job
	j = models.ingest_workspace_job.query.filter_by(id=job_package['job_id']).first()

	# instatitate object instance
	o = models.ingest_workspace_object(j, object_title=job_package['object_title'], DMDID=job_package['DMDID'])

	# set type
	o.object_type = job_package['object_type']

	# fill out object row with information from job_package
	o.ingest_id = job_package['ingest_id']

	# structMap
	o.struct_map = job_package['struct_map']

	# MODS file
	if job_package['MODS_temp_filename']:
		with open(job_package['MODS_temp_filename'], 'r') as fhand:
			o.MODS = fhand.read()
			os.remove(job_package['MODS_temp_filename'])
	else:
		o.MODS = None

	# add and commit(for now)
	return o._commit()


#################################################################################
# Create Bag 
#################################################################################

@celery.task(name="createBag_factory")
def createBag_factory(job_package):
	
	print "FIRING createBag_factory"
	
	# DEBUG
	# print job_package

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


	############################################################################################################
	# If file path included, reindex files
	# parse and index files, add to job rows
	if form_data['files_location'] != '':

		# get job
		j = models.ingest_workspace_job.query.filter_by(id=int(form_data['job_id'])).first()
		print "adding file index for %s" % j.name
		time.sleep(5)

		print "updating file index for bags"
		fd = {}
		for root, directories, files in os.walk (form_data['files_location'], followlinks=False):
			for filename in files:
				filePath = os.path.join(root,filename)
				print "adding",filePath
				fd[filename] = filePath

		# add to job in MySQL
		j.file_index = json.dumps(fd)
		j._commit()
	############################################################################################################

	# insert into MySQL as ingest_workspace_object rows
	step = 1
	time.sleep(2)
	for row in object_rows:

		print "Creating bag for ingest_id: %s, count %s / %s" % (row, step, len(object_rows))
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
def createBag_worker(job_package):

	print "FIRING createBag_worker"

	# DEBUG
	# print job_package

	# get form data
	form_data = job_package['form_data']

	# determine if purging old bags
	if 'purge_bags' in form_data and form_data['purge_bags'] == 'on':
		purge_bags = True
	else:
		purge_bags = False

	# get object row
	o = models.ingest_workspace_object.query.filter_by(ingest_id=job_package['ingest_id'],job_id=job_package['job_id']).first()
	print "Working on: %s" % o.object_title

	# load bag class
	print "loading bag class for %s" % form_data['bag_creation_class']	
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
		print "could not load MODS as etree element"

	# if not purging bags, and previous bag_path already found, skip
	if purge_bags == False and o.bag_path != None:
		print "skipping bag creation for %s / %s, already exists" % (o.object_title,o.DMDID)
		bag_result = False

	# else, create bags (either overwriting or creating new)
	else:
		# instantiate bag_class_worker from class
		if o.object_type == 'collection':
			print "firing collection object bag creator"
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

	print "FIRING ingestBag_factory"
	
	# DEBUG
	print job_package

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
	time.sleep(2)
	for row in object_rows:

		print "Preparing to ingest ingest_id: %s, count %s / %s" % (row, step, len(object_rows))
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
		
		result = actions.actions.custom_loop_taskWrapper.apply_async(kwargs={'job_package':job_package}, queue=job_package['username'])
		task_id = result.id

		# Set handle in Redis
		redisHandles.r_job_handle.set("%s" % (task_id), "FIRED,%s" % (step))
			
		# update incrementer for total assigned
		jobs.jobUpdateAssignedCount(job_package['job_num'])

		# bump step
		step += 1


@celery.task(name="ingestBag_callback")
def ingestBag_callback(job_package):
	
	print "FIRING ingestBag_callback"	

	# open handle
	o = models.ingest_workspace_object.query.filter_by(ingest_id=job_package['ingest_id'],job_id=job_package['job_id']).first()
	print "Retrieved row: %s / %s" % (o.ingest_id,o.object_title)
	print "Setting ingest JSON"
	o.ingested = job_package['form_data']['dest_repo']
	return o._commit()


#################################################################################
# Check Object Status
#################################################################################

@celery.task(name="checkObjectStatus_factory")
def checkObjectStatus_factory(job_package):
	
	print "FIRING checkObjectStatus_factory"

	# get form data
	form_data = job_package['form_data']	

	# set new task_name, for the worker below
	job_package['custom_task_name'] = 'checkObjectStatus_worker'

	# parse object rows from range (use parseIntSet() above)
	print form_data['object_id_range'].lower()
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

		print "Preparing to check object ingest_id: %s, count %s / %s" % (row, step, len(object_rows))
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
def checkObjectStatus_worker(job_package):

	print "FIRING checkObjectStatus_worker"

	# get form data
	form_data = job_package['form_data']

	# get object row
	o = models.ingest_workspace_object.query.filter_by(ingest_id=job_package['ingest_id'],job_id=job_package['job_id']).first()
	print "Checking status of: %s" % o.object_title

	# assume False commit
	to_commit = False

	# bag path
	if 'check_bag_path' in form_data and form_data['check_bag_path'] == 'on':
		print "checking bag path: %s" % o.bag_path
		if o.bag_path != None and os.path.exists(o.bag_path):
			print "bag_path found."
		else:
			o.bag_path = None
			to_commit = True

	
	# repo status
	if 'check_repo' in form_data and form_data['check_repo'] == 'on':
		print "checking existence in repository against %s" % form_data['dest_repo']
		
		# get fedora handle
		if form_data['dest_repo'] == 'local':
			dest_repo = fedora_handle
		else:
			dest_repo = fedoraHandles.remoteRepo(form_data['dest_repo'])

		# check status
		check_result = dest_repo.get_object(o.pid).exists
		print "existence check: %s" % check_result

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
# Utilities
#################################################################################

def rowQueryBuild(job_id, session):

	# begin query definition
	query = db.session.query(models.ingest_workspace_object).filter(models.ingest_workspace_object.job_id == job_id)

	# row start
	if "row_s" in session and "row_e" in session:
		print "adding row range filter"
		query = query.filter(models.ingest_workspace_object.ingest_id >= session['row_s'])
		query = query.filter(models.ingest_workspace_object.ingest_id <= session['row_e'])

	# ingested status
	if 'ingested' in session:
		print "adding ingest filter"
		if session['ingested'] == "None":
			query = query.filter(or_(models.ingest_workspace_object.ingested == None, models.ingest_workspace_object.ingested == "0" ))
		else:
			query = query.filter(models.ingest_workspace_object.ingested == session['ingested'])

	# bag created
	if 'no_bag_path' in session:
		print "adding bag created filter"
		query = query.filter(or_(models.ingest_workspace_object.bag_path == None, models.ingest_workspace_object.bag_path == "0" ))

	# return query object
	return query


def currentRowsSet(job_id,session):
	print 'determining all current rows after filter, setting as selection'
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
		print "Invalid set: " + str(invalid)
	return selection

