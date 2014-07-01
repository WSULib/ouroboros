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


DCfromMODS = Blueprint('DCfromMODS', __name__, template_folder='templates', static_folder="static")

@DCfromMODS.route('/DCfromMODS')
def index():	
	return redirect("/fireTask/DCfromMODS_worker")

def DCfromMODS_worker(job_package):
	PID = job_package['PID']

	# 1) download MODS datastream
	##################################################################################################################	
	print "Downloading: {PID} MODS datastream...".format(PID=PID)
	response = urllib.urlopen("http://localhost/fedora/objects/{PID}/datastreams/MODS/content".format(PID=PID))	
	MODS = response.read()
	XMLroot = etree.fromstring(MODS)

	# 2) transform downloaded MODS to DC with LOC stylesheet
	##################################################################################################################		
	print "XSLT Transforming: {PID}".format(PID=PID)
	# Saxon transformation
	XSLhand = open('inc/xsl/MODS_to_DC.xsl','r')		
	xslt_tree = etree.parse(XSLhand)
	transform = etree.XSLT(xslt_tree)
	DC = transform(XMLroot)

	# 3) create DC datastream
	##################################################################################################################
	'''
	Consider using EULfedora here...
	'''

	# unesacpe PID
	PID = PID.replace("\:", ":")		
	print "Creating Datastream for: {PID}".format(PID=PID)

	#baseURL
 	baseFedoraURL = "http://localhost/fedora/objects/{PID}/datastreams/DC?".format(PID=PID)
	print baseFedoraURL

 	# set parameters
 	fedoraParams = {
 	'controlGroup':'M',	
 	'dsLabel':'DC',
 	'mimeType':'text/xml'
 	} 	

 	headers = {'Content-Type': 'application/xml'}
	response = requests.post(baseFedoraURL, auth=('fedoraAdmin', 'cowp00p2012'), params=fedoraParams, data=str(DC), headers=headers)
 	if response.status_code == 201:
 		print "DC from MODS derivation successful"
	else:
		print "Unsuccessful transformation.  Need to elevate this to exception..."