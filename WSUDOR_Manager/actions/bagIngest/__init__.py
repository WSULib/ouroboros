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

from flask import Blueprint, render_template, abort, request, redirect, session

#python modules
from lxml import etree
import re
import json

# eulfedora
import eulfedora

# import bagit
import bagit

# create blueprint
bagIngest = Blueprint('bagIngest', __name__, template_folder='templates', static_folder="static")


# main view
@bagIngest.route('/bagIngest', methods=['POST', 'GET'])
def index():

	# form = forms.bagIngestForm()	

	return render_template("bagIngestIndex.html")


# # singleBag view
# @bagIngest.route('/bagIngest/singleBag', methods=['POST', 'GET'])
# def singleBag_index():

# 	if request.args.get('bag_dir'):		
# 		payload = request.args.get('bag_dir')
# 		singleBag_ingest_worker.delay(payload)

# 	return render_template("singleBagIndex.html")

# # ingest singleBag
# @celery.task(name="singleBag_ingest_worker")
# def singleBag_ingest_worker(payload):	

# 	# load bag_handle
# 	bag_dir = payload
# 	print "Working on:",bag_dir
# 	bag_handle = WSUDOR_ContentTypes.WSUDOR_Object(object_type="bag",payload=bag_dir)
	
# 	# validate bag for WSUDOR ingest	
# 	valid_results = bag_handle.validIngestBag()
# 	if valid_results['verdict'] != True:
# 		print "Bag is not valid for the following reasons, aborting."
# 		print valid_results
# 		return False

# 	# ingest bag
# 	ingest_bag = bag_handle.ingestBag()
# 	return ingest_bag# ingest singleBag


#############################################################################

# singleBag view
@bagIngest.route('/bagIngest/singleBag', methods=['POST', 'GET'])
def singleBag_index():	

	return render_template("singleBagIndex.html")


@bagIngest.route('/bagIngest/singleBag/fire', methods=['POST', 'GET'])
def singleBag_ingest():	
	# get new job num
	job_num = jobs.jobStart()

	# get username
	username = session['username']			

	# prepare job_package for boutique celery wrapper
	job_package = {
		'job_num':job_num,
		'task_name':"singleBag_ingest_worker",
		'form_data':request.form
	}	

	# job celery_task_id
	celery_task_id = celeryTaskFactoryUnique.delay(job_num,job_package)		 

	# send job to user_jobs SQL table
	db.session.add(models.user_jobs(job_num, username, celery_task_id, "init"))	
	db.session.commit()		

	print "Started job #",job_num,"Celery task #",celery_task_id
	return redirect("/userJobs")



@celery.task(name="celeryTaskFactoryUnique")
def celeryTaskFactoryUnique(job_num,job_package):

	print job_package
	
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
		
	# update incrementer for total assigned
	jobs.jobUpdateAssignedCount(job_num)

	# bump step
	step += 1



def singleBag_ingest_worker(job_package):	

	# load bag_handle
	bag_dir = job_package['form_data']['bag_dir']
	print "Working on:",bag_dir
	bag_handle = WSUDOR_ContentTypes.WSUDOR_Object(object_type="bag",payload=bag_dir)
	
	# validate bag for WSUDOR ingest	
	valid_results = bag_handle.validIngestBag()
	if valid_results['verdict'] != True:
		print "Bag is not valid for the following reasons, aborting."
		print valid_results
		return False

	# ingest bag
	ingest_bag = bag_handle.ingestBag()
	return json.dumps({"Ingest Results for {bag_label}, PID: {bag_pid}".format(bag_label=bag_handle.label,bag_pid=bag_handle.pid):ingest_bag})







