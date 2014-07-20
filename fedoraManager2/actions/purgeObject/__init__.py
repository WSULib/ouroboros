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
from flask import Blueprint, render_template, redirect, abort, request, session

from fedoraManager2.fedoraHandles import fedora_handle
from fedoraManager2.jobs import getSelPIDs
from fedoraManager2 import utilities


purgeObject = Blueprint('purgeObject', __name__, template_folder='templates', static_folder="static")


@purgeObject.route('/purgeObject')
def index():

	# get PIDs	
	PIDs = getSelPIDs()
	return render_template("purgeObject.html")


@purgeObject.route('/purgeObject/confirm', methods=['POST','GET'])
def confirm():	

	form_data = request.form

	pin_package = {
		"an1": form_data['an1'],
		"ap1": form_data['ap1'],
		"an2": form_data['an2'],
		"ap2": form_data['ap2']
	}

	#check admin credentials	
	confirm_status = utilities.checkPinCreds(pin_package,"purge")	

	return render_template("purgeConfirm.html",confirm_status=confirm_status,pin_package=pin_package)



def purgeObject_worker(job_package):	

	form_data = job_package['form_data']

	PID = job_package['PID']

	# check credentials
	pin_package = {
		"an1": form_data['an1'],
		"ap1": form_data['ap1'],
		"an2": form_data['an2'],
		"ap2": form_data['ap2']
	}
	confirm_status = utilities.checkPinCreds(pin_package,"purge")
	if confirm_status == False:
		return "Skipping, admin credentials don't check out."

	# check object state
	obj_handle = fedora_handle.get_object(PID)
	print obj_handle.state
	if obj_handle.state != "D":
		return "Skipping, object state not 'Deleted (D)'"
	
	# else, purge object from Fedora (object will be pulled via Messenging service)
	result = fedora_handle.purge_object(PID)
	return "{PID} purge result: {result}".format(PID=PID,result=result)



