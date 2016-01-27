from cl.cl import celery
from celery import Task
import redis

import WSUDOR_Manager.jobs as jobs
import WSUDOR_Manager.redisHandles as redisHandles
import WSUDOR_Manager.models as models
from WSUDOR_Manager import app
from flask import session

# local dependecies
import time
import sys


# action blueprints
###########################################################################

# register blueprints
tasks_URL_prefix = "/tasks"

#iiifManifest Management
from iiifManifest import iiifManifest, iiifManifestGenerate_worker
app.register_blueprint(iiifManifest, url_prefix=tasks_URL_prefix)

#solrIndexer
from solrIndexer import solrIndexer_blue
app.register_blueprint(solrIndexer_blue, url_prefix=tasks_URL_prefix)

#exportObject to objectBag
from exportObject import exportObject, exportObject_worker
app.register_blueprint(exportObject, url_prefix=tasks_URL_prefix)

#ingestBag
from bagIngest import bagIngest, bagIngest_worker 
app.register_blueprint(bagIngest, url_prefix=tasks_URL_prefix)

#bagIngestAndPush
from bagIngestAndPush import bagIngestAndPush, bagIngestAndPush_worker 
app.register_blueprint(bagIngestAndPush, url_prefix=tasks_URL_prefix)

#createObjectIndex
from createObjectIndex import createObjectIndex
app.register_blueprint(createObjectIndex, url_prefix=tasks_URL_prefix)

#MODSexport
from MODSexport import MODSexport, importMODS_worker
app.register_blueprint(MODSexport, url_prefix=tasks_URL_prefix)

#editDSXMLAdv
from editDSMime import editDSMime, editDSMime_worker
app.register_blueprint(editDSMime, url_prefix=tasks_URL_prefix)

#editDSXMLAdv
from editDSXMLAdv import editDSXMLAdv, editDSXMLAdv_worker
app.register_blueprint(editDSXMLAdv, url_prefix=tasks_URL_prefix)

#editDSRegex
from editDSRegex import editDSRegex, editDSRegex_regex_worker
app.register_blueprint(editDSRegex, url_prefix=tasks_URL_prefix)

#manageOAI
from manageOAI import manageOAI, manageOAI_genItemID_worker, manageOAI_toggleSet_worker, exposeToDPLA_worker, removeFromDPLA_worker
app.register_blueprint(manageOAI, url_prefix=tasks_URL_prefix)

#editRELS
from editRELS import editRELS, editRELS_add_worker, editRELS_purge_worker, editRELS_modify_worker, editRELS_edit_worker, editRELS_regex_worker
app.register_blueprint(editRELS, url_prefix=tasks_URL_prefix)

#DCfromMODS
from DCfromMODS import DCfromMODS, DCfromMODS_worker, DCfromMODS_single
app.register_blueprint(DCfromMODS, url_prefix=tasks_URL_prefix)

#addDS
from addDS import addDS, addDS_worker
app.register_blueprint(addDS, url_prefix=tasks_URL_prefix)

#purgeDS
from purgeDS import purgeDS, purgeDS_worker
app.register_blueprint(purgeDS, url_prefix=tasks_URL_prefix)

#batchIngest
from batchIngest import batchIngest, ingestFOXML_worker
app.register_blueprint(batchIngest, url_prefix=tasks_URL_prefix)

#objectState
from objectState import objectState, objectState_worker
app.register_blueprint(objectState, url_prefix=tasks_URL_prefix)

#objectState
from purgeObject import purgeObject, purgeObject_worker
app.register_blueprint(purgeObject, url_prefix=tasks_URL_prefix)

#checksum
from checksum import checksum, checksum_worker
app.register_blueprint(checksum, url_prefix=tasks_URL_prefix)

#createManifest
from createManifest import createManifest
app.register_blueprint(createManifest, url_prefix=tasks_URL_prefix)

#createManifest
from createBag import createBag
app.register_blueprint(createBag, url_prefix=tasks_URL_prefix)

#genericMethod
from genericMethod import genericMethod_worker

#createManifest
from objectRefresh import objectRefresh
app.register_blueprint(objectRefresh, url_prefix=tasks_URL_prefix)


# task firing
###########################################################################

# Fires *after* task is complete
class postTask(Task):
	abstract = True
	def after_return(self, *args, **kwargs):		

		# extract task data		
		status = args[0]
		task_id = args[2]
		task_details = args[3]		
		job_num = task_details[0]['job_num']
		PID = task_details[0]['PID']

		# release PID from PIDlock
		redisHandles.r_PIDlock.delete(PID)		

		# update job with task completion
		redisHandles.r_job_handle.set("{task_id}".format(task_id=task_id), "{status},{PID}".format(status=status,PID=PID))		
	
		# increments completed tasks
		if status == "SUCCESS":
			jobs.jobUpdateCompletedCount(job_num)		


@celery.task(name="celeryTaskFactory")
def celeryTaskFactory(**kwargs):
	
	# create job_package
	job_package = kwargs['job_package']	

	# get username
	username = job_package['username']

	# get job_num
	job_num = kwargs['job_num']

	# get and iterate through user selectedPIDs			
	PIDlist = kwargs['PIDlist']	

	# task function for taskWrapper		
	job_package['task_name'] = kwargs['task_name']
	
	#set step counter
	step = 1		
		
	# iterate through PIDs 	
	for PID in PIDlist:
		time.sleep(.001)
					
		job_package['step'] = step	
		job_package['PID'] = PID

		# fire off async task via taskWrapper		
		result = taskWrapper.delay(job_package)		
		task_id = result.id

		# Set handle in 
		redisHandles.r_job_handle.set("{task_id}".format(task_id=task_id), "FIRED,{PID}".format(PID=PID))
			
		# update incrementer for total assigned
		jobs.jobUpdateAssignedCount(job_num)

		# bump step
		step += 1		

	print "Finished assigning tasks"


#TASKS
##################################################################
@celery.task(base=postTask,bind=True,max_retries=3,name="taskWrapper")
def taskWrapper(self,job_package,*args, **kwargs):
	
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
		 
		

	







