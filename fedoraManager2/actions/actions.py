from cl.cl import celery
from celery import Task
import redis

import fedoraManager2.jobs as jobs
import fedoraManager2.redisHandles as redisHandles
import fedoraManager2.models as models

# local dependecies
import time
import sys

# import tasks
from fedoraManager2.actions.fileWrite.fileWrite import fileWrite
from fedoraManager2.actions.sampleTasks import sampleTask, sampleFastTask

# Fires *after* task is complete
class postTask(Task):
	abstract = True
	def after_return(self, *args, **kwargs):		

		# extract task data		
		status = args[0]
		task_id = args[2]
		task_details = args[3]
		step = task_details[0]['step']
		job_num = task_details[0]['job_num']
		PID = task_details[0]['PID']

		# release PID from PIDlock
		redisHandles.r_PIDlock.delete(PID)		

		# update job with task completion				
		redisHandles.r_job_handle.set("task{step}_job_num{job_num}".format(step=step,job_num=job_num), status)	
	
		# increments completed tasks
		jobs.jobUpdateCompletedCount(job_num)


@celery.task()
def celeryTaskFactory(**kwargs):	
	
	# create job_package
	job_package = kwargs['job_package']
	print job_package['jobHand'].assigned_tasks

	# get username
	username = job_package['username']

	# get job_num
	job_num = kwargs['job_num']

	# get and iterate through user selectedPIDs			
	PIDlist = kwargs['PIDlist']	

	# task function for taskWrapper	
	job_package['task_function'] = kwargs['task_function']
	
	#set step counter
	step = 1		
		
	# iterate through PIDs 	
	for PID in PIDlist:
		time.sleep(.001)		

		# OLD, WORKING
		# print "Operating on PID:",PID," / Step:",step		
		job_package['step'] = step	
		job_package['PID'] = PID		
		# fire off async task via taskWrapper		
		result = taskWrapper.delay(job_package)		
		task_id = result.id		
		redisHandles.r_job_handle.set("task{step}_job_num{job_num}".format(step=job_package['step'],job_num=job_package['job_num']), "FIRED")
			
		# update incrementer for total assigned
		jobs.jobUpdateAssignedCount(job_num)

		# bump step
		step += 1		

	print "Finished assigning tasks"


#TASKS
##################################################################
'''
max_retries = 100
countdown defaulting to 3 seconds
	- stressed with same PID 50+ times over, seems pretty resilient to exceptions
'''
@celery.task(base=postTask,bind=True,max_retries=100)
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
		funcName = job_package['task_function']	
		return funcName(job_package)

	







