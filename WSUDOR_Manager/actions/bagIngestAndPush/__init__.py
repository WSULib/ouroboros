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

try:
	from inc import repocp
except:
	print "could not load repocp script"

from flask import Blueprint, render_template, abort, request, redirect, session

#python modules
from lxml import etree
import re
import json
import os
import tarfile
import uuid
import requests

# eulfedora
import eulfedora

# import bagit
import bagit

# localConfig
import localConfig

# create blueprint
bagIngestAndPush = Blueprint('bagIngestAndPush', __name__, template_folder='templates', static_folder="static")


# main view
@bagIngestAndPush.route('/bagIngestAndPush', methods=['POST', 'GET'])
def index():

	return render_template("bagIngestAndPushIndex.html", REMOTE_REPOSITORIES=localConfig.REMOTE_REPOSITORIES)


# singleBag worker
@bagIngestAndPush.route('/bagIngestAndPush/ingest', methods=['POST', 'GET'])
def bagIngestAndPush_router():	

	# get new job num
	job_num = jobs.jobStart()

	# get username
	username = session['username']			

	# prepare job_package for boutique celery wrapper
	job_package = {
		'job_num':job_num,
		'task_name':"bagIngestAndPush_worker",
		'form_data':request.form
	}	

	# job celery_task_id
	celery_task_id = celeryTaskFactorybagIngestAndPush.delay(job_num,job_package)		 

	# send job to user_jobs SQL table
	db.session.add(models.user_jobs(job_num, username, celery_task_id, "init", "singleBagItIngest"))	
	db.session.commit()		

	print "Started job #",job_num,"Celery task #",celery_task_id
	return redirect("/userJobs")



@celery.task(name="celeryTaskFactorybagIngestAndPush")
def celeryTaskFactorybagIngestAndPush(job_num,job_package):
	
	# reconstitute
	job_num = job_package['job_num']	

	# update job info
	redisHandles.r_job_handle.set("job_{job_num}_est_count".format(job_num=job_num),1)

	# ingest in Fedora
	step = 1

	job_package['PID'] = "N/A"
	job_package['step'] = step		

	# fire ingester
	result = actions.actions.taskWrapper.delay(job_package)	

	task_id = result.id		
	print task_id
		
	# update incrementer for total assigned
	jobs.jobUpdateAssignedCount(job_num)

	# bump step
	step += 1


def bagIngestAndPush_worker(job_package):	

	# get form data
	form_data = job_package['form_data']
	if "ingest_type" in form_data:
		ingest_type = form_data['ingest_type']
	else:
		return "No ingest type selected, aborting."

	if ingest_type == "single":
		singleBag_ingest_worker(job_package)

	if ingest_type == "multiple":
		multipleBag_ingest_worker(job_package)


def singleBag_ingest_worker(job_package):
	'''
	This function expects a single BagIt object, either directory or archive, for ingest.
	'''

	# extract payload_location
	payload_location = job_package['form_data']['payload_location']
	ingest_type = job_package['form_data']['ingest_type']
	if 'refresh_remote' in job_package['form_data']:
		refresh_remote = True
	else:
		refresh_remote = False

	# create working directory in workspace
	bag_dir = payloadExtractor(payload_location,ingest_type)

	return ingestBagAndPush(bag_dir,job_package['form_data']['dest_repo'],refresh_remote)



def multipleBag_ingest_worker(job_package):

	'''
	This function expects multiple BagIt objects, either directory or archive, for ingest.	
	'''

	# extract payload_location
	payload_location = job_package['form_data']['payload_location']
	ingest_type = job_package['form_data']['ingest_type']
	if 'refresh_remote' in job_package['form_data']:
		refresh_remote = True
	else:
		refresh_remote = False

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
			os.system("rm {archive_filename}".format(archive_filename=archive_filename))

		# finally, rewalk
		bag_dirs_tuple = os.walk(bag_dir).next()

	# dirs
	bag_dirs = [ bag_dirs_tuple[0] + "/" + bag_name for bag_name in bag_dirs_tuple[1] ]
	print bag_dirs

	# iterate through BagIt dirs
	count = 1
	for bag in bag_dirs:
		print "Ingesting {count} / {total}".format(count=count,total=len(bag_dirs))
		ingestBagAndPush(bag,job_package['form_data']['dest_repo'],refresh_remote)
		count += 1

	print "Batch ingest complete."
	return True


 
def payloadExtractor(payload_location,ingest_type):	
	
	'''
	function to detect archive or dir, extract where necessary, and return path (bag_dir) of extracted directory in workspace
	'''

	# payload as archive
	if os.path.isfile(payload_location):
		print "payload_location is a file, extracting archive of BagIt directory(s)"
		archive_filename = os.path.basename(payload_location)

		# move file
		os.system("cp {payload_location} /tmp/Ouroboros/ingest_workspace/".format(payload_location=payload_location))

		# extract to temp dir
		temp_dir = str(uuid.uuid4())
		tar_handle = tarfile.open("/tmp/Ouroboros/ingest_workspace/{archive_filename}".format(archive_filename=archive_filename))
		tar_handle.extractall(path="/tmp/Ouroboros/ingest_workspace/{temp_dir}".format(temp_dir=temp_dir))

		# remove archive after copy
		os.system("rm /tmp/Ouroboros/ingest_workspace/{archive_filename}".format(archive_filename=archive_filename))

		# extracted bag_dir for single, return directory of single BagIt directory
		if ingest_type == "single":
			bag_dir = os.walk("/tmp/Ouroboros/ingest_workspace/{temp_dir}".format(temp_dir=temp_dir)).next()[1][0]
			bag_dir = "/tmp/Ouroboros/ingest_workspace/{temp_dir}/".format(temp_dir=temp_dir) + bag_dir

		# extracted bag_dir for multiple, return temp directory full of BagIt archives
		if ingest_type == "multiple":
			bag_dir = "/tmp/Ouroboros/ingest_workspace/{temp_dir}".format(temp_dir=temp_dir)

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


		
def ingestBagAndPush(bag_dir, dest_repo, refresh_remote=True):

	# DEBUG
	print dir(localConfig)

	# load bag_handle and ingest	
	print "Working on:",bag_dir
	bag_handle = WSUDOR_ContentTypes.WSUDOR_Object(object_type="bag", payload=bag_dir)
	if bag_dir == 'Could not load WSUDOR or Bag object.':
		print "Aborting, bag_handle initiziation was unsuccessful."
		return False
	
	# validate bag for WSUDOR ingest	
	valid_results = bag_handle.validIngestBag()
	if valid_results['verdict'] != True:
		print "Bag is not valid for the following reasons, aborting.", valid_results
		return False

	# ingest bag & skip indexing
	ingest_bag = bag_handle.ingestBag(indexObject=False)

	# push to remote repo

	# external script
	# print "sending object..."
	# push_cmd = 'python /opt/eulfedora/scripts/repo-cp --config %s %s %s %s' % (localConfig.REMOTE_REPOSITORIES_CONFIG_FILE, localConfig.REPOSITORY_NAME, dest_repo, bag_handle.pid)
	# print push_cmd
	# os.system(push_cmd)

	# import as library
	print "sending object..."
	result = repocp.repo_copy(config=localConfig.REMOTE_REPOSITORIES_CONFIG_FILE,source=localConfig.REPOSITORY_NAME, dest=dest_repo, pids=[bag_handle.pid])


	# delete local object
	print "finally, removing object"
	fedora_handle.purge_object(bag_handle.pid)

	# remove from Solr	
	solr_handle.delete_by_key(bag_handle.pid)

	# refresh object in remote repo (requires refreshObject() method in remote Ouroboros)
	if refresh_remote:
		print "refreshing remote object in remote repository"
		refresh_remote_url = '%s/tasks/objectRefresh/%s' % (localConfig.REMOTE_REPOSITORIES[dest_repo]['OUROBOROS_BASE_URL'], bag_handle.pid)
		print refresh_remote_url
		r = requests.get( refresh_remote_url )
		print r.content
	else:
		print "skipping remote refresh"	

	return json.dumps({"Ingest Results for {bag_label}, PID: {bag_pid}".format(bag_label=bag_handle.label.encode('utf-8'),bag_pid=bag_handle.pid):True})


