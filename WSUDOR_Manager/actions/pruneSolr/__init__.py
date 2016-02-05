# utility to prune from Solr what is not in Fedora

# celery
from cl.cl import celery

# handles
from WSUDOR_Manager.solrHandles import solr_handle
from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager import redisHandles, jobs, models, db
from flask import Blueprint, render_template, abort, request, redirect, session

#python modules
import json

pruneSolr = Blueprint('pruneSolr', __name__, template_folder='templates', static_folder="static")

'''
Improvement: use pagination in results, not hardcoded rows count
'''

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

	# get all solr objects
	sr = solr_handle.search(q='*:*',rows=10000)

	# iterate through
	count = 0
	pruned = []
	for doc in sr.documents:
		print "%i / %i" % (count, int(sr.total_results))
		doc_id = doc['id']
		print "checking", doc_id

		if not fedora_handle.get_object(doc_id).exists:
			print "We did not find it, pruning from Solr"
			pruned.append(doc_id)
			solr_handle.delete_by_key(doc_id)

		count+=1

	print "Pruned:",pruned

	# return JSON report
	return json.dumps(pruned)









