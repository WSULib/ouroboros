#!/usr/bin/env python
import requests
import json
import sys
import os
import datetime
import time
from flask import Blueprint, render_template, redirect, abort, request
from flask.ext.login import login_required

import WSUDOR_ContentTypes
from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager import celery, utilities, roles, redisHandles, jobs
import WSUDOR_Manager.actions as actions

import localConfig


diagnostics = Blueprint('diagnostics', __name__, template_folder='templates', static_folder="static")


@diagnostics.route('/diagnostics', methods=['GET', 'POST'])
@login_required
@roles.auth(['admin','metadata'])
def index():	

	# render
	return render_template("diagnostics.html")



@diagnostics.route('/diagnostics/front_end_postman', methods=['GET', 'POST'])
@login_required
@roles.auth(['admin','metadata'])
def front_end_postman():	

	'''
	Form that configures and submits postman tests for running as background job
	'''

	# check for run reports
	reports = [f for f in os.listdir("/tmp/Ouroboros") if f.startswith('postman_report_')]

	# render
	return render_template("front_end_postman.html", reports=reports)


@celery.task(name="front_end_postman_factory")
def front_end_postman_factory(job_package):

	'''
	receives postman job to run	
	'''

	# get form data
	form_data = job_package['form_data']	

	# set new task_name, for the worker below
	job_package['custom_task_name'] = 'front_end_postman_worker'

	# update job info (need length from above)
	redisHandles.r_job_handle.set("job_%s_est_count" % (job_package['job_num']), 1)

	# fire task via custom_loop_taskWrapper			
	result = actions.actions.custom_loop_taskWrapper.apply_async(kwargs={'job_package':job_package}, queue=job_package['username'])
	task_id = result.id

	# Set handle in Redis
	redisHandles.r_job_handle.set("%s" % (task_id), "FIRED,%s" % (form_data['report_name']))
		
	# update incrementer for total assigned
	jobs.jobUpdateAssignedCount(job_package['job_num'])


@celery.task(name="front_end_postman_worker")
@roles.auth(['admin','metadata'], is_celery=True)
def front_end_postman_worker(job_package):

	'''
	receives postman job to run	
	target command: newman run https://raw.githubusercontent.com/WSULib/ouroboros/v2/inc/postman/WSUDOR.postman_collection.json -e https://raw.githubusercontent.com/WSULib/ouroboros/v2/inc/postman/WSUDOR.postman_environment.json -r html --reporter-html-export /tmp/Ouroboros/postman_report_[REPORT_NAME].json
	'''

	# get form data
	form_data = job_package['form_data']	
	print "running postman front-end tests, report: %s" % form_data['report_name']

	# run newman job, exports to /tmp/Ouroboros
	cmd = "newman run https://raw.githubusercontent.com/WSULib/ouroboros/v2/inc/postman/WSUDOR.postman_collection.json -e https://raw.githubusercontent.com/WSULib/ouroboros/v2/inc/postman/WSUDOR.postman_environment.json -r json --reporter-json-export /tmp/Ouroboros/postman_report_%s.json -n %s" % (form_data['report_name'],form_data['iterations'])
	os.system(cmd)

	# # open results
	'''
	Consider data parsing here?  If long, would make sense to do so here instead of page load for report view
	'''
	# time.sleep(1)
	# with open('/tmp/Ouroboros/postman_report_%s.json' % form_data['report_name']) as f:
	# 	report_json = json.loads(f.read())

	return json.dumps({
		"msg": "check for reports here: http://%s/%s/tasks/diagnostics/front_end_postman" % (localConfig.APP_HOST, localConfig.APP_PREFIX)
	})


@diagnostics.route('/diagnostics/front_end_postman/view_report/<report_name>', methods=['GET', 'POST'])
@login_required
@roles.auth(['admin','metadata'])
def front_end_postman_view(report_name):

	# load report
	print "loading /tmp/Ouroboros/%s" % report_name
	with open('/tmp/Ouroboros/%s' % report_name) as f:
		report_json = json.loads(f.read())

	# parse results and prepare for graph

	# DEBUG
	line_data = [34, 43, 65, 23, 76, 32, 34]

	# render
	return render_template("front_end_postman_view_report.html", line_data=line_data)



