#!/usr/bin/env python
import requests
import json
import sys
import os
import datetime
from flask import Blueprint, render_template, redirect, abort, request
from flask.ext.login import login_required

import WSUDOR_ContentTypes
from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager import celery, utilities, roles, redisHandles
import WSUDOR_Manager.actions as actions


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

	# render
	return render_template("front_end_postman.html")


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
	'''

	# get form data
	form_data = job_package['form_data']
	print "running postman front-end tests, report: %s" % form_data['report_name']
	return True






