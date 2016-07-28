# code related to jobs

# dep
import redis
import pickle
import time
# proj
import models
from redisHandles import *
from WSUDOR_Manager import db, celery, models
from flask import session

# Job Management
############################################################################################################
def jobStart():
	'''Consider SQL, might be more enduring'''
	# increment and get job num
	job_num = r_job_handle.incr("job_num")	
	# add timestamp for start time
	r_job_handle.set("job_%s_stime" % (job_num),int(time.time()))
	return job_num


def jobUpdateAssignedCount(job_num):
	r_job_handle.incr("job_%s_assign_count" % (job_num))


def jobUpdateCompletedCount(job_num):
	r_job_handle.incr("job_%s_complete_count" % (job_num))


def getTaskDetails(task_id):
	return celery.AsyncResult(task_id)


def updateLocalJob(job_num,est_tasks,assign_tasks,completed_tasks):

	# send task to redis
	redisHandles.r_job_handle.set("%s,%s" % (job_num, step), "FIRED,%s,%s" % (task_id, PID))


# function to remove job from fm2
def jobRetire_worker(job_num):	
	# get job handle
	job_query = models.user_jobs.query.filter_by(job_num=job_num)

	# set status to "retired"
	job_query[0].status = "retired"
	
	# commit
	return db.session.commit()


# function to remove job from fm2
def jobRemove_worker(job_num):	

	# get job handle
	job_query = models.user_jobs.query.filter_by(job_num=job_num)
	job_handle = job_query.first()
	
	# get children from job	
	job_celery_id = job_handle.celery_task_id

	# get children
	job_celery_handle = celery.AsyncResult(job_celery_id)
	children = job_celery_handle.children

	# remove celery results from Redis backend
	to_delete = []	
	for child in children:
		to_delete.append(child.id)	
	
	task_del_num = r_job_handle.delete(*to_delete)
	task_del_result = "%s tasks remove from Redis backend" % (task_del_num)	

	# remove from SQL DB	
	db_del_result = job_query.delete()
	if db_del_result == 1:
		db_del_result = "Job %s removed from SQL DB" % (job_num)
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
	print "Storing selected PIDs for %s" % (username)

	# insert into table via list comprehension
	values_groups = [(each.encode('ascii'), username.encode('ascii'), False, group_name) for each in PIDs]
	values_groups_string = str(values_groups)[1:-1] # trim brackets			
	db.session.execute("INSERT INTO user_pids (PID,username,status,group_name) VALUES %s" % (values_groups_string));
	db.session.commit()	

	print "PIDs stored"		
	etime = time.time()
	ttime = (etime - stime) * 1000
	print "Took this long to add PIDs to SQL",ttime,"ms"


# PID removal
def removeUserPIDs(username,PIDs):
	stime = time.time()	
	print "Removing selected PIDs for %s" % (username)	
	
	# delete from table
	targets_tuple = tuple([each.encode('ascii') for each in PIDs])	
	db.session.execute("DELETE FROM user_pids WHERE PID in %s" % (targets_tuple));
	db.session.commit()

	etime = time.time()
	ttime = (etime - stime) * 1000
	print "Took this long to remove PIDs to SQL",ttime,"ms"
	print "PIDs removed"	

'''
Improvement for getSelPIDs() and genPIDlet() - creator generator that suffices both?
'''

def getSelPIDs(username=False):
	if not username:
		username = session['username']
	userSelectedPIDs = models.user_pids.query.filter_by(username=username,status=True)	
	PIDlist = [PID.PID for PID in userSelectedPIDs]
	return PIDlist

# function to create small object with current, previous, and next PIDs for views
def genPIDlet(cursor):

	# get PIDs
	PIDs = getSelPIDs()

	# set to zero if out of bounds
	if cursor > len(PIDs) or cursor < 0:
		PIDlet = False
		return PIDlet

	# init dict
	PIDlet = {
		"cPID" : PIDs[cursor],
		"count" : len(PIDs)
	}		
	
	# only one
	if len(PIDs) == 1:
		PIDlet["pPID"] = None
		PIDlet["nPID"] = None

	# first one
	elif cursor <= 0:		
		PIDlet["pPID"]  = None
		PIDlet["nPID"] = PIDs[cursor+1]
		
	# last one	
	elif cursor >= (len(PIDs) - 1):		
		PIDlet["pPID"] = PIDs[cursor-1]
		PIDlet["nPID"] = None	

	# somewhere mid-range
	else:
		PIDlet["pPID"] = PIDs[cursor-1]			
		PIDlet["nPID"] = PIDs[cursor+1]			

	return PIDlet
	

# function to get PIDs from ingest workspace job
def getIWPIDs(job_num):

	return models.ingest_workspace_object.query.filter_by(job=models.ingest_workspace_job.query.filter_by(id=job_num).first())



















