from WSUDOR_Manager import celery
from celery import Task
import redis

import WSUDOR_Manager.jobs as jobs
import WSUDOR_Manager.redisHandles as redisHandles
import WSUDOR_Manager.models as models
from WSUDOR_Manager import app, db, logging
from flask import session


# local dependecies
import time
import sys

# action blueprints
###########################################################################

# register blueprints
tasks_URL_prefix = "/tasks"

#addDS
from addDS import addDS, addDS_worker
app.register_blueprint(addDS, url_prefix=tasks_URL_prefix)

#aem
from aem import aem
app.register_blueprint(aem, url_prefix=tasks_URL_prefix)

#ingestBag
from bagIngest import bagIngest, bagIngest_factory, bagIngest_worker 
app.register_blueprint(bagIngest, url_prefix=tasks_URL_prefix)

#checkJP2
from checkJP2 import checkJP2, checkJP2_worker
app.register_blueprint(checkJP2, url_prefix=tasks_URL_prefix)

#createManifest
from createBag import createBag
app.register_blueprint(createBag, url_prefix=tasks_URL_prefix)

#createLearningObj
from createLearningObj import createLearningObj
app.register_blueprint(createLearningObj, url_prefix=tasks_URL_prefix)

#createManifest
from createManifest import createManifest
app.register_blueprint(createManifest, url_prefix=tasks_URL_prefix)

#createObj
from createObj import createObj
app.register_blueprint(createObj, url_prefix=tasks_URL_prefix)

#createObjectIndex
from createObjectIndex import createObjectIndex
app.register_blueprint(createObjectIndex, url_prefix=tasks_URL_prefix)

#diagnostics
from diagnostics import diagnostics, front_end_postman_factory, front_end_postman_worker
app.register_blueprint(diagnostics, url_prefix=tasks_URL_prefix)

#DCfromMODS
from DCfromMODS import DCfromMODS, DCfromMODS_worker, DCfromMODS_single
app.register_blueprint(DCfromMODS, url_prefix=tasks_URL_prefix)

#editDSXMLAdv
from editDSMime import editDSMime, editDSMime_worker
app.register_blueprint(editDSMime, url_prefix=tasks_URL_prefix)

#editDSRegex
from editDSRegex import editDSRegex, editDSRegex_regex_worker
app.register_blueprint(editDSRegex, url_prefix=tasks_URL_prefix)

#editRELS
from editRELS import editRELS, editRELS_add_worker, editRELS_purge_worker, editRELS_modify_worker, editRELS_edit_worker, editRELS_regex_worker
app.register_blueprint(editRELS, url_prefix=tasks_URL_prefix)

#exportObject to objectBag
from exportObject import exportObject, exportObject_worker
app.register_blueprint(exportObject, url_prefix=tasks_URL_prefix)

#genericMethod
from genericMethod import genericMethod_worker

#iiifManifest Management
from iiifManifest import iiifManifest, iiifManifestGenerate_worker
app.register_blueprint(iiifManifest, url_prefix=tasks_URL_prefix)

#ingestWorkspace
from ingestWorkspace import ingestWorkspace, createJob_factory, createJob_worker, createBag_factory, createBag_worker, ingestBag_factory, ingestBag_callback, checkObjectStatus_factory, checkObjectStatus_worker, aem_factory, aem_worker
app.register_blueprint(ingestWorkspace, url_prefix=tasks_URL_prefix)

#manageOAI
from manageOAI import manageOAI, exposeToDPLA_worker, removeFromDPLA_worker
app.register_blueprint(manageOAI, url_prefix=tasks_URL_prefix)

#MODSexport
from MODSexport import MODSexport, MODSimport_factory, MODSimport_worker
app.register_blueprint(MODSexport, url_prefix=tasks_URL_prefix)

#objectRefresh
from objectRefresh import objectRefresh
app.register_blueprint(objectRefresh, url_prefix=tasks_URL_prefix)

#purgeDS
from purgeDS import purgeDS, purgeDS_worker
app.register_blueprint(purgeDS, url_prefix=tasks_URL_prefix)

#objectState
from objectState import objectState, objectState_worker
app.register_blueprint(objectState, url_prefix=tasks_URL_prefix)

#pruneSolr
from pruneSolr import pruneSolr, pruneSolr_factory, pruneSolr_worker
app.register_blueprint(pruneSolr, url_prefix=tasks_URL_prefix)

#purgeObject
from purgeObject import purgeObject, purgeObject_worker
app.register_blueprint(purgeObject, url_prefix=tasks_URL_prefix)

#sendObject
from sendObject import sendObject, sendObject_worker
app.register_blueprint(sendObject, url_prefix=tasks_URL_prefix)


# Fires *after* task is complete
class postTask(Task):
	abstract = True
	def after_return(self, *args, **kwargs):		

		# extract task data		
		status = args[0]
		task_id = args[2]
		job_package = args[4]['job_package']
		job_num = job_package['job_num']

		# obj_loop jobs
		##################################################################
		if job_package['job_type'] == 'obj_loop':
			logging.debug("Cleaning up for obj_loop task")
			PID = job_package['PID']
			# release PID from PIDlock
			redisHandles.r_PIDlock.delete(PID)
			# update job with task completion
			redisHandles.r_job_handle.set(task_id, "%s,%s" % (status,PID))		

		# custom_loop jobs
		##################################################################
		if job_package['job_type'] == 'custom_loop':
			logging.debug("Cleaning up for custom_loop task")
			redisHandles.r_job_handle.set(task_id, status)

		# increments completed tasks		
		jobs.jobUpdateCompletedCount(job_num)



# obj_loop TASK FACTORY
##################################################################
@celery.task(name="obj_loop_taskFactory",trail=True)
def obj_loop_taskFactory(**kwargs):

	# create job_package
	job_package = kwargs['job_package']

	# username
	username = job_package['username']

	# get job_num
	job_num = kwargs['job_num']

	# get and iterate through user selectedPIDs			
	PIDlist = kwargs['PIDlist']	

	# task function for obj_loop_taskWrapper		
	job_package['task_name'] = kwargs['task_name']
	
	#set step counter
	step = 1		
		
	# iterate through PIDs 	
	for PID in PIDlist:
		time.sleep(.001)
					
		job_package['step'] = step	
		job_package['PID'] = PID

		# fire off async task via obj_loop_taskWrapper		
		result = obj_loop_taskWrapper.apply_async(kwargs={'job_package':job_package,}, queue=username)
		task_id = result.id

		# Set handle in 
		redisHandles.r_job_handle.set("%s" % (task_id), "FIRED,%s" % (PID))
			
		# update incrementer for total assigned
		jobs.jobUpdateAssignedCount(job_num)

		# bump step
		step += 1		

	logging.debug("Finished assigning tasks")


@celery.task(base=postTask, bind=True, max_retries=3, name="obj_loop_taskWrapper",trail=True)
def obj_loop_taskWrapper(self, **kwargs):

	job_package = kwargs['job_package']
	
	# check PIDlock
	lock_status = redisHandles.r_PIDlock.exists(job_package['PID'])
	
	# if locked, divert
	if lock_status == True:
		time.sleep(.25)
		raise self.retry(countdown=3)
	else:
		redisHandles.r_PIDlock.set(job_package['PID'],1)	
		
		# execute function				
		'''
		For the most part, this fires functions that were imported directly from blueprints
		'''
		return globals()[job_package['task_name']](job_package)



# custom_loop TASK FACTORY
##################################################################
@celery.task(base=postTask,bind=True,max_retries=3,name="custom_loop_taskWrapper",trail=True)
def custom_loop_taskWrapper(self, *args, **kwargs):

	job_package = kwargs['job_package']
	
	# execute function				
	'''
	For the most part, this fires functions that were imported directly from blueprints.
	'''
	return globals()[job_package['custom_task_name']](job_package)




		 
		

	







