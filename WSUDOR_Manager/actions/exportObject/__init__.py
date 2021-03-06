#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
import json
import sys
import ast
import os
import xml.etree.ElementTree as ET
import urllib, urllib2
import datetime
from lxml import etree
import uuid
import StringIO
import tarfile

from flask import Blueprint, render_template, redirect, abort, request, session

import eulfedora

from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager.jobs import getSelPIDs
from WSUDOR_Manager import utilities, roles
import WSUDOR_ContentTypes


exportObject = Blueprint('exportObject', __name__, template_folder='templates', static_folder="static")

'''
This action is designed to export a given object as a WSUDOR objectBag, an instance of LOC's BagIt standard.
'''


@exportObject.route('/exportObject')
@utilities.objects_needed
@roles.auth(['admin','metadata'])
def index():	

	# get PIDs	
	PIDs = getSelPIDs()
	return render_template("exportObject.html")


@roles.auth(['admin','metadata'], is_celery=True)
def exportObject_worker(job_package):	 

	export_result = WSUDOR_ContentTypes.WSUDOR_Object(job_package['PID']).exportBag(job_package)
	return export_result


