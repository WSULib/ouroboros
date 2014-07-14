# code related to jobs

# dep
import redis
import pickle
import time
# proj
import models
from redisHandles import *
from fedoraManager2 import db, db_con
from cl.cl import celery
from flask import session

# Job Management
############################################################################################################
def jobStart():
	'''
	Consider MySQL, might be more enduring?
	'''
	# increment and get job num
	job_num = r_job_handle.incr("job_num")	
	return job_num

def jobUpdateAssignedCount(job_num):
	r_job_handle.incr("job_{job_num}_assign_count".format(job_num=job_num))

def jobUpdateCompletedCount(job_num):
	r_job_handle.incr("job_{job_num}_complete_count".format(job_num=job_num))

def getTaskDetails(task_id):
	return celery.AsyncResult(task_id)


# function for non-PID based jobs to fire job
def startLocalJob():
	'''
	1) get new job_num
	2) send anticipated tasks?
	3) update completed ones somewhere?
	'''

	#establish job_num
	job_num = jobStart()

	# send job to user_jobs SQL table
	username = session['username']	
	db.session.add(models.user_jobs(job_num,username, "init"))	
	db.session.commit() 


	new_job_package = {
		"job_num":job_num
	}

	return new_job_package

def updateLocalJob(job_num,est_tasks,assign_tasks,completed_tasks):

	# send task to redis
	redisHandles.r_job_handle.set("{job_num},{step}".format(step=step,job_num=job_num), "FIRED,{task_id},{PID}".format(task_id=task_id,PID=PID))

# function to remove job from fm2
def jobRemove_worker(job_num):	

	# get number of tasks	
	job_task_num = int(r_job_handle.get("job_{job_num}_est_count".format(job_num=job_num)))
	print "Number of tasks to remove for the job:",job_task_num	

	# remove from celery broker
	'''
	Might not be possible / necessary.  AsyncResult.forget() doesn't seem to have any effect... 
	Skipping for now.
	'''

	# remove celery results from Redis backend
	to_delete = []
	task_step = 1
	while task_step <= job_task_num:
		to_delete.append("{job_num},{task_step}".format(job_num=job_num,task_step=task_step))
		task_step += 1
	
	task_del_num = r_job_handle.delete(*to_delete)
	task_del_result = "{task_del_num} tasks remove from Redis backend".format(task_del_num=task_del_num)
	

	# remove from SQL DB
	job_handle = models.user_jobs.query.filter_by(job_num=job_num)
	db_del_result = job_handle.delete()
	if db_del_result == 1:
		db_del_result = "Job {job_num} removed from SQL DB".format(job_num=job_num)
	else:
		db_del_result = "Job Not Found"
	db.session.commit()

	# prepare return package
	result_package = (task_del_result,db_del_result)
	return result_package


# PID selection
############################################################################################################

# PID selection
def sendUserPIDs(username,PIDs,group_name):
	stime = time.time()	
	''' expecting username and list of PIDs'''
	print "Storing selected PIDs for {username}".format(username=username)

	# insert into table via list comprehension
	values_groups = [(each.encode('ascii'),username.encode('ascii'),'unselected',group_name) for each in PIDs]
	values_groups_string = str(values_groups)[1:-1] # trim brackets			
	db.session.execute("INSERT INTO user_pids (PID,username,status,group_name) VALUES {values_groups_string}".format(values_groups_string=values_groups_string));
	db.session.commit()	

	print "PIDs stored"		
	etime = time.time()
	ttime = (etime - stime) * 1000
	print "Took this long to add PIDs to SQL",ttime,"ms"


# PID removal
def removeUserPIDs(username,PIDs):
	stime = time.time()	
	print "Removing selected PIDs for {username}".format(username=username)	
	
	# delete from table
	targets_tuple = tuple([each.encode('ascii') for each in PIDs])	
	db.session.execute("DELETE FROM user_pids WHERE PID in {targets_tuple}".format(targets_tuple=targets_tuple));
	db.session.commit()

	etime = time.time()
	ttime = (etime - stime) * 1000
	print "Took this long to remove PIDs to SQL",ttime,"ms"
	print "PIDs removed"	


def getSelPIDs():
	username = session['username']
	userSelectedPIDs = models.user_pids.query.filter_by(username=username,status="selected")	
	PIDlist = [PID.PID for PID in userSelectedPIDs]
	return PIDlist
























