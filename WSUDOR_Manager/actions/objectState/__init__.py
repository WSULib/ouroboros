#!/usr/bin/env python
import requests
import json
import sys
import ast
import os
import xml.etree.ElementTree as ET
import urllib, urllib2
import datetime
from lxml import etree
from flask import Blueprint, render_template, redirect, abort

from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager import utilities, roles, logging


objectState = Blueprint('objectState', __name__, template_folder='templates', static_folder="static")


@objectState.route('/objectState')
@utilities.objects_needed
@roles.auth(['admin'])
def index():	
	return render_template("objectState.html")



@roles.auth(['admin'], is_celery=True)
def objectState_worker(job_package):
	form_data = job_package['form_data']
	logging.debug(form_data)

	# in confirmation present, change state
	if form_data['confirm_string'].lower() == "confirm":

		# grab target state
		target_state = form_data['target_state']

		# set state	
		logging.debug("Setting state to: %s" % (target_state))
		
		# get PID handle, set state, save()
		PID = job_package['PID']		
		obj_ohandle = fedora_handle.get_object(PID)		
		obj_ohandle.state = target_state
		return obj_ohandle.save()

	else:
		return "Confirmation not entered correctly, skipping."


