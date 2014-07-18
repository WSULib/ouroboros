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

from fedoraManager2.fedoraHandles import fedora_handle
from fedoraManager2.jobs import getSelPIDs


purgeObject = Blueprint('purgeObject', __name__, template_folder='templates', static_folder="static")


@purgeObject.route('/purgeObject')
def index():	

	# get PIDs	
	PIDs = getSelPIDs()		


	return render_template("purgeObject.html")



def purgeObject_worker(job_package):
	form_data = job_package['form_data']
	print form_data

	PID = job_package['PID']

	# check object state
	obj_handle = fedora_handle.get_object(PID)
	print obj_handle.state
	if obj_handle.state != "D":
		return "Skipping, object state not 'Deleted (D)'"

	
	return "PID purged (not yet actually)."


