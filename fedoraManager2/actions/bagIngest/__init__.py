# utility for Bag Ingest

# celery
from cl.cl import celery

# handles
from fedoraManager2.forms import RDF_edit
from fedoraManager2.solrHandles import solr_handle
from fedoraManager2.fedoraHandles import fedora_handle
from fedoraManager2 import redisHandles, jobs, models, db, forms, bags
import fedoraManager2.actions as actions
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


###############
# ROUTERS
###############


# main view
@bagIngest.route('/bagIngest', methods=['POST', 'GET'])
def index():

	# form = forms.bagIngestForm()	

	return render_template("bagIngestIndex.html")


# singleBag view
@bagIngest.route('/bagIngest/singleBag', methods=['POST', 'GET'])
def singleBag_index():

	if request.args.get('bag_dir'):		
		singleBag_ingest_worker(request)

	return render_template("singleBagIndex.html")



# ###############
# # JOB PREP
# ###############

# def singleBag_ingest(request):	
# 	# get new job num
# 	job_num = jobs.jobStart()

# 	# get username
# 	username = session['username']			

# 	# prepare job_package for boutique celery wrapper
# 	job_package = {
# 		'job_num':job_num,
# 		'form_data':request.args.get(),
# 		'task_name':"singleBag_ingest_worker"
# 	}	

# 	# job celery_task_id
# 	celery_task_id = celeryTaskFactoryUnique.delay(job_num,job_package)		 

# 	# send job to user_jobs SQL table
# 	db.session.add(models.user_jobs(job_num, username, celery_task_id, "init"))	
# 	db.session.commit()		

# 	print "Started job #",job_num,"Celery task #",celery_task_id
# 	return redirect("/userJobs")


# @celery.task(name="celeryTaskFactoryUnique")
# def celeryTaskFactoryUnique(job_num,job_package):
	
# 	# reconstitute
# 	form_data = job_package['form_data']
# 	job_num = job_package['job_num']
	
# 	# update job info
# 	redisHandles.r_job_handle.set("job_{job_num}_est_count".format(job_num=job_num),1) # hardcoded as 1 now, but could key off 

# 	job_package['PID'] = "N/A"

# 	# fire ingester
# 	print job_package
# 	result = actions.actions.taskWrapper.delay(job_package)
# 	task_id = result.id		
		
# 	# update incrementer for total assigned
# 	jobs.jobUpdateAssignedCount(job_num)

		




###############
# WORKERS
###############

# ingest singleBag
def singleBag_ingest_worker(request):

	print request.args		

	# load bag_handle
	bag_dir = "/tmp/Ouroboros/ingest_bags/"+request.args.get("bag_dir")
	print "Working on:",bag_dir
	bag_handle = bags.ingestBag(bag_dir)
	
	# quick validate
	print "Bag is valid:",bag_handle.Bag.validate()	

	# ingest bag, as determined by ojbMeta.content_model, and defined in bags.ingestBag
	ingest_bag = bag_handle.ingest()



# ingest singleBag
def collectionBag_ingest(request):	

	pass












