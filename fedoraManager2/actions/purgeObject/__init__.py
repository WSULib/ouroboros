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

	#check admin credentials	
	if form_data['admin_pin_1'] == utilities.genUserPin(form_data['admin_name_1']) and form_data['admin_pin_2'] == utilities.genUserPin(form_data['admin_name_2']) and form_data['admin_name_1'] != form_data['admin_name_2']:		
		confirm_status = True
		session['purge_confirm'] = True

	else:
		confirm_status = False
		session['purge_confirm'] = False

	return render_template("purgeConfirm.html",confirm_status=confirm_status)



def purgeObject_worker(job_package):
	
	# form_data = job_package['form_data']
	# print form_data	

	PID = job_package['PID']

	# check confirm_status in session
	# if session['purge_confirm'] != True:
	# 	return "Skipping, purge confirmation was not met."

	# check object state
	obj_handle = fedora_handle.get_object(PID)
	print obj_handle.state
	if obj_handle.state != "D":
		return "Skipping, object state not 'Deleted (D)'"

	
	return "PID purged (not yet actually)."


