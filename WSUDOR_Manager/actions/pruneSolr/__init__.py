# utility to prune from Solr what is not in Fedora

# celery
from cl.cl import celery

# handles
from WSUDOR_Manager.solrHandles import solr_handle
from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager import redisHandles, jobs, models, db, actions
from flask import Blueprint, render_template, abort, request, redirect, session

#python modules
import json

pruneSolr = Blueprint('pruneSolr', __name__, template_folder='templates', static_folder="static")


@pruneSolr.route('/pruneSolr', methods=['POST', 'GET'])
def index():

	# get new job num
	job_num = jobs.jobStart()

	# get username
	username = session['username']			

	# prepare job_package for boutique celery wrapper
	job_package = {
		'job_num':job_num,
		'task_name':"pruneSolr_worker"
	}	

	# job celery_task_id
	celery_task_id = celeryTaskFactoryBagIngest.delay(job_num,job_package)		 

	# send job to user_jobs SQL table
	db.session.add(models.user_jobs(job_num, username, celery_task_id, "init", "pruneSolr"))	
	db.session.commit()		

	print "Started job #",job_num,"Celery task #",celery_task_id
	return redirect("/userJobs")


@celery.task(name="celeryTaskFactoryBagIngest")
def celeryTaskFactoryBagIngest(job_num,job_package):
	
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


def pruneSolr_worker(job_package):		
	
	print "pruning Solr of objects not found in Fedora"

	# variables 
	count = 0
	pruned = []
	start = 0
	rows = 100

	# get solr results obj
	solr_total = solr_handle.search(q='*:*', fl='id').total_results

	# iterate through
	while start < solr_total:

		# perform search
		solr_result = solr_handle.search(q='*:*', fl='id', rows=rows, start=start)

		# iterate
		for doc in solr_result.documents:
			doc_id = doc['id']
			print "pruneSolr checking %s, %i / %i" % (doc_id, count, solr_total)

			if not fedora_handle.get_object(doc_id).exists:
				print "Did not find object in Fedora, pruning from Solr..."
				pruned.append(doc_id)
				solr_handle.delete_by_key(doc_id)

			# bump counter
			count+=1

		# bump start
		start += rows		

	# return JSON report
	return json.dumps(pruned)










