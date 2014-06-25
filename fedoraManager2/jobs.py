# code related to jobs

# dep
import redis
import pickle
import time
# proj
import models
from redisHandles import *
from fedoraManager2 import db, db_con

# Job Management
############################################################################################################
def jobStart():
	# increment and get job num
	job_num = r_job_handle.incr("job_num")
	print "Beginning job #",job_num

	# instatiate handles for job and status of tasks
	jobHand = models.jobBlob(job_num)
	taskHand = models.taskBlob(job_num)
	return {"jobHand":jobHand,"taskHand":taskHand}


# job objects
def jobUpdate(jobHand):
	jobHand_pickled = pickle.dumps(jobHand)
	r_job_handle.set("job_{job_num}".format(job_num=jobHand.job_num),jobHand_pickled)

def jobGet(job_num):	
	# IDEA: could query redis for r_job_handle.keys(job_num matching)!
	jobHand_pickled = r_job_handle.get("job_{job_num}".format(job_num=job_num))
	jobHand = pickle.loads(jobHand_pickled)	
	return jobHand

def jobUpdateAssignedCount(job_num):
	r_job_handle.incr("job_{job_num}_assign_count".format(job_num=job_num))

def jobUpdateCompletedCount(job_num):
	r_job_handle.incr("job_{job_num}_complete_count".format(job_num=job_num))

# task objects
def taskUpdate(taskHand):		
	taskHand_pickled = pickle.dumps(taskHand)				
	r_job_handle.set("taskStatus_{job_num}".format(job_num=taskHand.job_num),taskHand_pickled)	

def taskGet(job_num):
	taskHand_pickled = r_job_handle.get("taskStatus_{job_num}".format(job_num=job_num))
	taskHand = pickle.loads(taskHand_pickled)	
	# this is key, loads all tasks for a given job number
	completed_tasks = r_job_handle.keys("task*job_num{job_num}".format(job_num=job_num))
	taskHand.completed_tasks = 	completed_tasks	
	return taskHand


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






























