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

from WSUDOR_ContentTypes import WSUDOR_Object
from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager import utilities


checkJP2 = Blueprint('checkJP2', __name__, template_folder='templates', static_folder="static")


@checkJP2.route('/checkJP2')
@utilities.objects_needed
def index():	

	return render_template("checkJP2.html")



def checkJP2_worker(job_package):

	form_data = job_package['form_data']
	print form_data

	tests = []

	if 'codestream' in form_data:
		tests.append('codestream')

	if 'orientation' in form_data:
		tests.append('orientation')

	# fire tests
	o = WSUDOR_Object(job_package['PID'])
	return o.checkJP2(tests=tests, regenJP2_on_fail=True)

	


