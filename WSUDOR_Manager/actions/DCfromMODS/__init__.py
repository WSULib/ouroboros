#!/usr/bin/env python
from localConfig import *
from WSUDOR_Manager import utilities

import requests
import json
import sys
import ast
import os
import xml.etree.ElementTree as ET
import urllib, urllib2
import datetime
from lxml import etree
from flask import Blueprint, render_template, redirect, abort, url_for, session

# handles
from WSUDOR_Manager import roles
from WSUDOR_Manager.fedoraHandles import fedora_handle
import WSUDOR_ContentTypes


DCfromMODS = Blueprint('DCfromMODS', __name__, template_folder='templates', static_folder="static")

'''
With the function doing bulk and single, break the actual work in a function used by both.
'''

@DCfromMODS.route('/DCfromMODS')
@utilities.objects_needed
@roles.auth(['admin','metadata'])
def index():		
	return redirect(url_for('fireTask',job_type='obj_loop', task_name='DCfromMODS_worker'))


@DCfromMODS.route('/DCfromMODS/single/<PID>')
@roles.auth(['admin','metadata'])
def single(PID):
	return DCfromMODS_single(PID)


def DCfromMODS_single(PID):	

	obj = WSUDOR_ContentTypes.WSUDOR_Object(PID)
	return obj.DCfromMODS()


def DCfromMODS_worker(job_package):

	PID = job_package['PID']
	obj = WSUDOR_ContentTypes.WSUDOR_Object(PID)
	return obj.DCfromMODS()

	




