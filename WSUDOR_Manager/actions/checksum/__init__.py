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


checksum = Blueprint('checksum', __name__, template_folder='templates', static_folder="static")


@checksum.route('/checksum')
def index():	
	return render_template("checksum.html")



def checksum_worker(job_package):
	form_data = job_package['form_data']
	print form_data

	# in confirmation present, change state
	if form_data['confirm_string'] == "CONFIRM":

		# grab target state
		target_state = form_data['target_state']

		# set state	
		print "Setting state to: %s" % (target_state)
		
		# get PID handle, set state, save()
		PID = job_package['PID']		
		obj_ohandle = fedora_handle.get_object(PID)		
		obj_ohandle = obj_ohandle.ds_list
		for (name, loc) in obj_ohandle.items():
			print name

		# getDatastreamObject('ACCESS').checksum_type
		# getDatastreamObject('ACCESS').checksum
		# take name, insert into .checksum and checksum_type
		# return datastream name and checksum results to page (which are then sorted by template)
		# not quiet sure what return does below
		return obj_ohandle

		# Enable Checksumming feature to be developed if Checksums are not enabled

	else:
		return "Confirmation not entered correctly, skipping."


