#!/usr/bin/env python
# -*- coding: utf-8 -*-

# generic method

from flask import Blueprint, render_template, redirect, abort, request, session

import eulfedora

from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager.jobs import getSelPIDs, genPIDlet
from WSUDOR_Manager import utilities, redisHandles
import WSUDOR_ContentTypes
import localConfig

genericMethod = Blueprint('genericMethod', __name__, template_folder='templates', static_folder="static")

def genericMethod_worker(job_package):

	print "working on %s" % job_package['PID']

	# get object handle
	obj_handle = WSUDOR_ContentTypes.WSUDOR_Object(job_package['PID'])

	# get function from obj_handle	
	func = getattr(obj_handle, job_package['form_data']['method_name'])

	# fire function
	return func()	
