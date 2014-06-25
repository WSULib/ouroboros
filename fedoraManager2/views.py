# fm2
from fedoraManager2 import app
from fedoraManager2 import models
from fedoraManager2 import db
from fedoraManager2.actions import actions
from fedoraManager2 import redisHandles

# flask proper
from flask import render_template, request, session, redirect, make_response
from flask.ext.sqlalchemy import SQLAlchemy

import utilities

# forms
# OLD (mitten)
from flask_wtf import Form
from wtforms import TextField
# NEW (silo)
# from flask.ext.wtf import Form
# from wtforms.fields import TextField, BooleanField

# python modules
import time
import json
import pickle
import sys
from uuid import uuid4
import json
import unicodedata

# get celery instance / handle
from cl.cl import celery
import jobs
import forms
from redisHandles import *

# solr handles
from solrHandles import solr_handle


# fake session data
####################################
# set the secret key
app.secret_key = 'ShoppingHorse'
####################################


# GENERAL
#########################################################################################################
@app.route("/")
def index():
	if "username" in session:
		username = session['username']
	else:
		username = "User not set."
	return render_template("index.html",username=username)

@app.route('/userPage/<username>')
def userPage(username):
	# set username in session
	session['username'] = username	

	# info to render page
	userData = {}
	userData['username'] = username
	return render_template("userPage.html",userData=userData)


# MIGHT WORK WHEN WE HAVE USER LOGIN PAGE...
# @app.route('/userPage/')
# def userPage():
# 	# set username in session
# 	username = session['username']

# 	# info to render page
# 	userData = {}
# 	userData['username'] = username
# 	return render_template("userPage.html",userData=userData)

# JOB MANAGEMENT
#########################################################################################################

# fireTask is the factory that begins tasks from fedoraManager2.actions
# epecting task function name from actions module, e.g. "sampleTask"
@app.route("/fireTask/<task_name>")
def fireTask(task_name):
	print "Starting task request..."
	
	# get username from session (will pull from user auth session later)
	username = session['username']	
	# get total SELECTED PIDs associated with user
	# # start timer
	stime = time.time()
	userSelectedPIDs = models.user_pids.query.filter_by(username=username,status="selected")	
	PIDlist = []
	for PID in userSelectedPIDs:
		PIDlist.append(PID.PID)
	etime = time.time()
	ttime = (etime - stime) * 1000
	print "Took this long to create list from SQL query",ttime,"ms"

	# if no PIDs selected, abort
	if userSelectedPIDs.count() == 0:
		return "<p>No PIDs selected, try again.  Try selecting <a href='/PIDmanage'>here</a>.</p>"

	# instatiate jobHand object with incrementing job_num
	jobInit = jobs.jobStart()
	
	jobHand = jobInit['jobHand']
	taskHand = jobInit['taskHand']

	# get new job number
	job_num = jobHand.job_num

	# send job to user_jobs SQL table
	db.session.add(models.user_jobs(job_num,username, "init"))	
	db.session.commit() 
	
	# begin job
	print "Antipcating",userSelectedPIDs.count(),"tasks...."
	# set estimated
	redisHandles.r_job_handle.set("job_{job_num}_est_count".format(job_num=job_num),userSelectedPIDs.count())

	# create job_package
	job_package = {		
		"username":username,
		"job_num":job_num,
		"jobHand":jobHand		
	}

	# grab task from actions based on URL "task_name" parameter, using getattr	
	task_function = getattr(actions, task_name)

	# send to celeryTaskFactory in actions.py
	# iterates through PIDs and creates secondary async tasks for each
	# passing username, task_name, task_function as imported above, and job_package containing all the update handles		
	result = actions.celeryTaskFactory.delay(job_num=job_num,task_name=task_name,task_function=task_function,job_package=job_package,PIDlist=PIDlist)

	# preliminary update
	jobs.jobUpdate(jobHand)		
	jobs.taskUpdate(taskHand)

	print "Started job #",jobHand.job_num

	return redirect("/userJobs")


@app.route("/jobStatus/<job_num>")
def jobStatus(job_num):	
	'''
	Look into making this more detailed for the job, perhaps this is where the logs will be monitored
	This could be breakdown of success and errors too...
	COPY FROM USERJOBS, PREVIOUS CODE IS TOO OLD
	'''
	pass	


@app.route("/userJobs")
def userJobs():

	username = session['username']	

	# get user jobs
	user_jobs_list = models.user_jobs.query.filter(models.user_jobs.status != "complete", models.user_jobs.username == username)

	# return package
	return_package = []

	for job in user_jobs_list:

		job_num = job.job_num

		# create package
		status_package = {}
		status_package["job_num"] = job_num #this is pulled from SQL table
		
		# get estimated tasks
		job_est_count = redisHandles.r_job_handle.get("job_{job_num}_est_count".format(job_num=job_num))
		# get assigned tasks
		job_assign_count = redisHandles.r_job_handle.get("job_{job_num}_assign_count".format(job_num=job_num))
		if job_assign_count == None:
			job_assign_count = 0
		# get completed tasks
		job_complete_count = redisHandles.r_job_handle.get("job_{job_num}_complete_count".format(job_num=job_num))
		if job_complete_count == None:
			job_complete_count = 0

		# spooling, works on stable jobHand object
		if job_assign_count > 0 and job_assign_count < job_est_count :
			# print "Job spooling..."
			status_package['job_status'] = "spooling"
			job.status = "spooling"

		# check if pending
		elif job_complete_count == 0:
			# print "Job Pending, waiting for others to complete.  Isn't that polite?"
			status_package['job_status'] = "pending"	
			job.status = "pending"	

		# check if completed
		elif job_complete_count == job_est_count:						
			status_package['job_status'] = "complete"	
			# udpate job status in SQL db here
			job.status = "complete"
			print "Job Complete!  Updated in SQL."

		# else, must be running
		else:
			status_package['job_status'] = "running"	

		# data return 
		response_dict = {
			"job_num":job_num,
			"job_status":status_package['job_status'],
			"assigned_tasks":job_assign_count,
			"completed_tasks":job_complete_count,
			"estimated_tasks":job_est_count
		}

		# return_package[status_package["job_num"]] = response_dict		
		return_package.append(response_dict)

	# commit all changes to SQL db
	db.session.commit()

	# return return_package
	if request.args.get("data","") == "true":
		json_string = json.dumps(return_package)
		resp = make_response(json_string)
		resp.headers['Content-Type'] = 'application/json'
		return resp
	else:
		return render_template("userJobs.html",username=session['username'])


@app.route("/userAllJobs")
def userAllJobs():

	username = session['username']

	# get user jobs
	user_jobs_list = models.user_jobs.query.filter(models.user_jobs.username == username)

	# return package
	return_package = []

	for job in user_jobs_list:

		job_package = {}
		job_package['job_num'] = job.job_num		
		job_package['status'] = job.status

		# push to return package
		return_package.append(job_package)
		
	return render_template("userAllJobs.html",username=session['username'],return_package=return_package)


@app.route("/task_status/<task_id>")
def task_status(task_id):
	
	# global way to surgically pick task out of celery memory		
	result = actions.celery.AsyncResult(task_id)	
	state, retval = result.state, result.result
	response_data = dict(id=task_id, status=state, result=retval)
	
	return json.dumps(response_data)	

# PID MANAGEMENT
####################################################################################

# @app.route("/PIDselection")
# def PIDselection():
# 	# get username from session
# 	username = session['username']
# 	return render_template('PIDselection.html', username=username)


# @app.route("/PIDenter", methods=['POST', 'GET'])
# def PIDenter():	

# 	# get username from session
# 	username = session['username']
# 	form = forms.PIDselection(request.form)

# 	if request.method == 'POST':		 
# 		PID = form.PID.data				
# 		jobs.sendUserPIDs(username,PID)
# 		return redirect("/PIDmanage")		

# 	return render_template('PIDformSQL.html', username=username, form=form)# PID selection sandboxing


# PID check for user
@app.route("/PIDmanage")
def PIDmanage():	
	# get username from session
	username = session['username']

	# gen group list	
	user_pid_groups = db.session.query(models.user_pids).filter(models.user_pids.username == username).group_by("group_name")
	group_names = [each.group_name.encode('ascii','ignore') for each in user_pid_groups]	

	# pass the current PIDs to page as list	
	return render_template("PIDSQL.html",username=username, group_names=group_names)



@app.route("/PIDmanageAction/<action>", methods=['POST', 'GET'])
def PIDmanageAction(action):	
	# get username from session
	username = session['username']
	print "Current action is:",action

	# if post AND group toggle
	if request.method == 'POST' and action == 'group_toggle':		
		group_name = request.form['group_name']
		db.session.execute("UPDATE user_pids SET status = CASE WHEN status = 'unselected' THEN 'selected' ELSE 'unselected' END WHERE username = '{username}' AND group_name = '{group_name}';".format(username=username,group_name=group_name))

	# select all
	if action == "s_all":
		print "All PIDs selected..."		
		db.session.query(models.user_pids).filter(models.user_pids.username == username).update({'status': "selected"})
	
	# select none
	if action == "s_none":
		print "All PIDs unselected..."
		db.session.query(models.user_pids).filter(models.user_pids.username == username).update({'status': "unselected"})
	
	# select toggle	
	if action == "s_toggle":		
		print "All PIDs toggling..."
		db.session.execute("UPDATE user_pids SET status = CASE WHEN status = 'unselected' THEN 'selected' ELSE 'unselected' END WHERE username = '{username}';".format(username=username))
	
	# delete selections
	if action == "s_del":
		db.session.query(models.user_pids).filter(models.user_pids.username == username, models.user_pids.status == "selected").delete()

	# commit changes
	db.session.commit()

	return "Update Complete."

	# pass the current PIDs to page as list	
	return redirect("/PIDmanage")


@app.route("/PIDRowUpdate/<id>/<action>/<status>")
def PIDRowUpdate(id,action,status):
	# get username from session
	username = session['username']

	# update single row status
	if action == "update_status":
		# get PID with query
		PID = models.user_pids.query.filter(models.user_pids.id == id)[0]
		# update
		if status == "toggle":
			# where PID.status equals current status in SQL
			if PID.status == "unselected":
				PID.status = "selected"
			elif PID.status == "selected":
				PID.status = "unselected"
		else:
			PID.status = status
		

	# delete single row
	if action == "delete":
		# get PID with query
		PID = models.user_pids.query.filter(models.user_pids.id == id)[0]
		db.session.delete(PID)
		print "Deleted PID id#",id,"from SQL database"

	# commit
	db.session.commit()	

	return "PID updated."


# PID selection via Solr
@app.route("/PIDSolr", methods=['POST', 'GET'])
def PIDSolr():	
	'''
	Current Approach: If POST, send results as large array to template, save as JS variable
		- works great so far at 800+ items, but what about 100,000+?
		- documentation says ~ 50,000 is the limit
		- will need to think of a server-side option
	'''
	# get username from session
	username = session['username']

	# get form
	form = forms.solrSearch(request.form)

	# dynamically update fields

	# collection selection
	coll_query = {'q':"rels_hasContentModel:*Collection", 'fl':["id","dc_title"], 'rows':1000}
	coll_results = solr_handle.search(**coll_query)
	coll_docs = coll_results.documents
	form.collection_object.choices = [(each['id'].encode('ascii','ignore'), each['dc_title'][0].encode('ascii','ignore')) for each in coll_docs]
	form.collection_object.choices.insert(0,("","All Collections"))	

	# content model
	cm_query = {'q':'*', 'facet' : 'true', 'facet.field' : 'rels_hasContentModel'}
	cm_results = solr_handle.search(**cm_query)	
	form.content_model.choices = [(each, each.split(":")[-1]) for each in cm_results.facets['facet_fields']['rels_hasContentModel']]
	form.content_model.choices.insert(0,("","All Content Types"))

	# perform search	
	if request.method == 'POST':
		
		# build base with native Solr queries
		query = {'q':form.q.data, 'fq':[form.fq.data], 'fl':[form.fl.data], 'rows':100000}
				
		# Fedora RELS-EXT
		# collection selection
		if form.collection_object.data:			
			print "Collection refinement:",form.collection_object.data						
			escaped_coll = form.collection_object.data.replace(":","\:") 
			query['fq'].append("rels_isMemberOfCollection:info\:fedora/"+escaped_coll)				


		# content model / type selection
		if form.content_model.data:			
			print "Content Model refinement:",form.content_model.data
			escaped_cm = form.content_model.data.replace(":","\:") 
			query['fq'].append("rels_hasContentModel:"+escaped_cm)				

		

		# issue query
		print query
		stime = time.time() 
		q_results = solr_handle.search(**query)
		etime = time.time()
		ttime = (etime - stime) * 1000
		print "Solr Query took:",ttime,"ms"		
		output_dict = {}
		data = []
		stime = time.time()
		for each in q_results.documents:
			try:			
				PID = each['id'].encode('ascii','ignore')
				dc_title = each['dc_title'][0].encode('ascii','ignore')
				data.append([PID,dc_title])
			except:				
				print "Could not render:",each['id'] #unicdoe solr id
		etime = time.time()
		ttime = (etime - stime) * 1000
		print "Solr Munging for DataTables took::",ttime,"ms"		

		output_dict['data'] = data
		json_output = json.dumps(data)

		return render_template("PIDSolr.html",username=username, form=form, q_results=q_results, json_output=json_output, coll_docs=coll_docs)		

	# pass the current PIDs to page as list	
	return render_template("PIDSolr.html",username=username, form=form, coll_docs=coll_docs)


# PID check for user
@app.route("/updatePIDsfromSolr/<update_type>", methods=['POST', 'GET'])
def updatePIDsfromSolr(update_type):	
	# get username from session
	username = session['username']	
	print "Sending PIDs to",username

	# retrieve PIDs
	PIDs = request.form['json_package']
	PIDs = json.loads(PIDs)	

	# get PIDs group_name
	group_name = request.form['group_name'].encode('ascii','ignore')

	# add PIDs to SQL
	if update_type == "add":		
		jobs.sendUserPIDs(username,PIDs,group_name)		
	
	# remove PIDs from SQL
	if update_type == "remove":
		print "removing each PID from SQL..."
		jobs.removeUserPIDs(username,PIDs)
		print "...complete."

	return "Update Complete."
	



######################################################
# Catch all - DON'T REMOVE
######################################################
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):    
	return render_template("404.html")













