# utility for Bag Ingest

# celery
from WSUDOR_Manager import celery

# handles
from WSUDOR_Manager.forms import RDF_edit
from WSUDOR_Manager.solrHandles import solr_handle
from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager import redisHandles, jobs, models, db, forms, roles
import WSUDOR_Manager.actions as actions
import WSUDOR_ContentTypes
import localConfig

from flask import Blueprint, render_template, abort, request, redirect, session

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
bagIngest = Blueprint('bagIngest', __name__, template_folder='templates', static_folder="static")


# main view
@bagIngest.route('/bagIngest', methods=['POST', 'GET'])
@roles.auth(['admin'])
def index():

	return render_template("bagIngestIndex.html", REMOTE_REPOSITORIES=localConfig.REMOTE_REPOSITORIES)


@celery.task(name="bagIngest_factory")
@roles.auth(['admin'], is_celery=True)
def bagIngest_factory(job_package):

	# get form data
	form_data = job_package['form_data']
	if "ingest_type" in form_data:
		ingest_type = form_data['ingest_type']
	else:
		return "No ingest type selected, aborting."

	# set new task_name, for the worker below
	job_package['custom_task_name'] = 'bagIngest_worker'

	
	# Single Ingest Type
	#################################################################
	if ingest_type == "single":

		payload_location = job_package['form_data']['payload_location']
		# create working directory in workspace
		bag_dir = payloadExtractor(payload_location,ingest_type)
		job_package['bag_dir'] = bag_dir

		# set estimated tasks
		print "Antipcating 1 tasks...."	
		redisHandles.r_job_handle.set("job_%s_est_count" % (job_package['job_num']), 1)

		step = 1

		result = actions.actions.custom_loop_taskWrapper.apply_async(kwargs={'job_package':job_package}, queue=job_package['username'])
		task_id = result.id

		# Set handle in Redis
		redisHandles.r_job_handle.set("%s" % (task_id), "FIRED,%s" % (bag_dir))
			
		# update incrementer for total assigned
		jobs.jobUpdateAssignedCount(job_package['job_num'])

		# bump step
		step += 1

		print "Finished firing ingest workers"


	# Multiple Ingest Type
	#################################################################
	if ingest_type == "multiple":

		# extract payload_location
		payload_location = job_package['form_data']['payload_location']

		# create working directory in workspace
		bag_dir = payloadExtractor(payload_location,ingest_type)
		if bag_dir == False:
			print "Aborting"
			return False
		print "Bag dir at this point:",bag_dir

		# all items inside bag_dir	
		bag_dirs_tuple = os.walk(bag_dir).next()

		# dirs
		if len(bag_dirs_tuple[1]) > 0:
			print "Directories detected, continuing"

		# archives
		if len(bag_dirs_tuple[2]) > 0:
			print "Archive files detected. Extracting and continuing."
			for archive in bag_dirs_tuple[2]:
				archive_filename = bag_dirs_tuple[0] + "/" + archive
				print archive_filename

				# extract to temp dir
				tar_handle = tarfile.open(archive_filename)
				tar_handle.extractall(path=bag_dirs_tuple[0])
				os.system("rm %s" % (archive_filename))

			# finally, rewalk
			bag_dirs_tuple = os.walk(bag_dir).next()

		# dirs
		bag_dirs = [ bag_dirs_tuple[0] + "/" + bag_name for bag_name in bag_dirs_tuple[1] ]
		print bag_dirs

		# set estimated tasks
		print "Antipcating",len(bag_dirs),"tasks...."	
		redisHandles.r_job_handle.set("job_%s_est_count" % (job_package['job_num']), len(bag_dirs))

		# iterate through bags
		step = 1
		for bag_dir in bag_dirs:
			print "Ingesting %s / %s" % (step, len(bag_dirs))
			job_package['bag_dir'] = bag_dir
			
			# fire task via custom_loop_taskWrapper			
			result = actions.actions.custom_loop_taskWrapper.apply_async(kwargs={'job_package':job_package}, queue=job_package['username'])
			task_id = result.id

			# Set handle in Redis
			redisHandles.r_job_handle.set("%s" % (task_id), "FIRED,%s" % (bag_dir))
				
			# update incrementer for total assigned
			jobs.jobUpdateAssignedCount(job_package['job_num'])

			# bump step
			step += 1

		print "Finished firing ingest workers"


@roles.auth(['admin'], is_celery=True)
def bagIngest_worker(job_package):
	
	bag_dir = job_package['bag_dir']

	# load bag_handle and ingest	
	print "Working on:",bag_dir
	bag_handle = WSUDOR_ContentTypes.WSUDOR_Object(bag_dir, object_type="bag")
	if bag_dir == 'Could not load WSUDOR or Bag object.':
		print "Aborting, bag_handle initiziation was unsuccessful."
		return False

	# validate bag for WSUDOR ingest	
	valid_results = bag_handle.validIngestBag()
	if valid_results['verdict'] != True:
		print "Bag is not valid for the following reasons, aborting.", valid_results
		return False

	# optional flags
	###########################################################################################
	# overwrite
	if 'overwrite' in job_package['form_data']:
		print "purging object if exists"
		if fedora_handle.get_object(bag_handle.pid).exists:
			fedora_handle.purge_object(bag_handle.pid)

	# push to remote
	if 'push_remote' in job_package['form_data']:

		# get options
		# set destination repo
		dest_repo = job_package['form_data']['dest_repo']

		# get export context
		export_context = job_package['form_data']['export_context']

		# overwrite
		if 'overwrite' in job_package['form_data']:
			overwrite = True
		else:
			overwrite = False

		# refresh remote
		if 'refresh_remote' in job_package['form_data']:
			refresh_remote = True
		else:
			refresh_remote = False

		# omit checksums
		if 'omit_checksums' in job_package['form_data']:
			omit_checksums = True
		else:
			omit_checksums = False

		# ingest bag
		try:
			# because we're sending remotely, not indexing locally
			ingest_bag = bag_handle.ingestBag()
		except Exception, e:
			raise Exception(e)
			return False

		# push to remote repo
		print "sending object..."

		# Use object method
		obj_handle = WSUDOR_ContentTypes.WSUDOR_Object(bag_handle.pid)
		obj_handle.sendObject(dest_repo, refresh_remote=refresh_remote, overwrite=overwrite, export_context=export_context, omit_checksums=omit_checksums)	

		# delete local object (and constituent objects)
		print "purging Constituents if present"
		if getattr(obj_handle, 'purgeConstituents', None):
			obj_handle.purgeConstituents()

		print "finally, removing object"
		fedora_handle.purge_object(obj_handle.pid)

		# remove from Solr	
		solr_handle.delete_by_key(obj_handle.pid)

		# fire ingestWorkspace callback if checked
		if 'origin' in job_package['form_data'] and job_package['form_data']['origin'] == 'ingestWorkspace' and ingest_bag == True:
			print "firing ingest callback"			
			actions.actions.ingestBag_callback.apply_async(kwargs={'job_package':job_package}, queue=job_package['username'])

		return json.dumps({"Ingest Results for %s, PID: %s" % (bag_handle.label.encode('utf-8'), bag_handle.pid):ingest_bag})


	else:
		# ingest bag
		try:
			ingest_bag = bag_handle.ingestBag()
			# fire ingestWorkspace callback if checked
			if 'origin' in job_package['form_data'] and job_package['form_data']['origin'] == 'ingestWorkspace' and ingest_bag == True:
				print "firing ingest callback"
				actions.actions.ingestBag_callback.apply_async(kwargs={'job_package':job_package}, queue=job_package['username'])
			return json.dumps({"Ingest Results for %s, PID: %s" % (bag_handle.label.encode('utf-8'), bag_handle.pid):ingest_bag})
		except Exception, e:
			raise Exception(e)
			return False


# UTILITIES
#################################################################
def payloadExtractor(payload_location,ingest_type):	
	
	'''
	function to detect archive or dir, extract where necessary, and return path (bag_dir) of extracted directory in workspace
	'''

	# payload as archive
	if os.path.isfile(payload_location):
		print "payload_location is a file, extracting archive of BagIt directory(s)"
		archive_filename = os.path.basename(payload_location)

		# move file
		os.system("cp %s /tmp/Ouroboros/ingest_workspace/" % (payload_location))

		# extract to temp dir
		temp_dir = str(uuid.uuid4())
		tar_handle = tarfile.open("/tmp/Ouroboros/ingest_workspace/%s" % (archive_filename))
		tar_handle.extractall(path="/tmp/Ouroboros/ingest_workspace/%s" % (temp_dir))

		# remove archive after copy
		os.system("rm /tmp/Ouroboros/ingest_workspace/%s" % (archive_filename))

		# extracted bag_dir for single, return directory of single BagIt directory
		if ingest_type == "single":
			bag_dir = os.walk("/tmp/Ouroboros/ingest_workspace/%s" % (temp_dir)).next()[1][0]
			bag_dir = "/tmp/Ouroboros/ingest_workspace/%s/" % (temp_dir) + bag_dir

		# extracted bag_dir for multiple, return temp directory full of BagIt archives
		if ingest_type == "multiple":
			bag_dir = "/tmp/Ouroboros/ingest_workspace/%s" % (temp_dir)

		return bag_dir


	# payload as directory
	elif os.path.isdir(payload_location):
		print "payload_location is a dir, no extraction required"
		bag_dir = payload_location
		return bag_dir


	# payload not file or dir
	else:
		print "payload_location does not appear to be a valid directory or file, or cannot be found at all.  Aborting."
		return False

