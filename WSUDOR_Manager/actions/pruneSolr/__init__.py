# utility to prune from Solr what is not in Fedora

# celery
from WSUDOR_Manager import celery

# handles
from WSUDOR_Manager.solrHandles import solr_handle
from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager import redisHandles, jobs, models, db, actions
from flask import Blueprint, render_template, abort, request, redirect, session

#python modules
import json

pruneSolr = Blueprint('pruneSolr', __name__, template_folder='templates', static_folder="static")



@celery.task(name="pruneSolr_factory")
def pruneSolr_factory(job_package):

	# set new task_name, for the worker below
	job_package['custom_task_name'] = 'pruneSolr_worker'

	# get solr results obj
	solr_total = solr_handle.search(q='*:*', fl='id').total_results

	# set estimated tasks
	print "Antipcating",solr_total,"tasks...."	
	redisHandles.r_job_handle.set("job_%s_est_count" % (job_package['job_num']), solr_total)

	# iterate through solr objects
	# variables 
	start = 0
	rows = 100
	step = 1
	while start < solr_total:

		# perform search
		solr_result = solr_handle.search(q='*:*', fl='id', rows=rows, start=start)

		# iterate
		for doc in solr_result.documents:
			doc_id = doc['id']
			print "pruneSolr checking %s" % (doc_id)

			job_package['doc_id'] = doc_id
			
			# fire task via custom_loop_taskWrapper			
			result = actions.actions.custom_loop_taskWrapper.apply_async(kwargs={'job_package':job_package}, queue=job_package['username']
			)
			task_id = result.id

			# Set handle in Redis
			redisHandles.r_job_handle.set("%s" % (task_id), "FIRED,%s" % (doc_id))
				
			# update incrementer for total assigned
			jobs.jobUpdateAssignedCount(job_package['job_num'])

			# bump step
			step += 1

		# bump start
		start += rows
	


@celery.task(name="pruneSolr_worker")
def pruneSolr_worker(job_package, PID=False):

	if PID:
		# prune specific PID
		solr_handle.delete_by_key(PID)
		return "PRUNED"

	else:
		doc_id = job_package['doc_id']
		
		if not fedora_handle.get_object(doc_id).exists:
			print "Did not find object in Fedora, pruning from Solr..."
			solr_handle.delete_by_key(doc_id)
			return "PRUNED"
		else:
			return "IGNORED"







