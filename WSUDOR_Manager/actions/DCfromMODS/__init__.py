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
from flask import Blueprint, render_template, redirect, abort, url_for

# handles
from WSUDOR_Manager.fedoraHandles import fedora_handle


DCfromMODS = Blueprint('DCfromMODS', __name__, template_folder='templates', static_folder="static")

'''
With the function doing bulk and single, break the actual work in a function used by both.
'''

@DCfromMODS.route('/DCfromMODS')
@utilities.objects_needed
def index():		
	return redirect(url_for('fireTask',job_type='obj_loop', task_name='DCfromMODS_worker'))


@DCfromMODS.route('/DCfromMODS/single/<PID>')
def single(PID):
	return DCfromMODS_single(PID)


def DCfromMODS_single(PID):	

	ohandle = fedora_handle.get_object(PID)

	# retrieve MODS		
	MODS_handle = ohandle.getDatastreamObject('MODS')		
	XMLroot = etree.fromstring(MODS_handle.content.serialize())

	# 2) transform downloaded MODS to DC with LOC stylesheet
	print "XSLT Transforming: %s" % (PID)
	# Saxon transformation
	XSLhand = open('inc/xsl/MODS_to_DC.xsl','r')		
	xslt_tree = etree.parse(XSLhand)
	transform = etree.XSLT(xslt_tree)
	DC = transform(XMLroot)		

	# 3) save to DC datastream
	DS_handle = ohandle.getDatastreamObject("DC")
	DS_handle.content = str(DC)
	derive_results = DS_handle.save()
	print "DCfromMODS result:",derive_results
	return derive_results
	


def DCfromMODS_worker(job_package):

	PID = job_package['PID']
	ohandle = fedora_handle.get_object(PID)

	# retrieve MODS		
	MODS_handle = ohandle.getDatastreamObject('MODS')		
	XMLroot = etree.fromstring(MODS_handle.content.serialize())

	# 2) transform downloaded MODS to DC with LOC stylesheet
	print "XSLT Transforming: %s" % (PID)
	# Saxon transformation
	XSLhand = open('inc/xsl/MODS_to_DC.xsl','r')		
	xslt_tree = etree.parse(XSLhand)
	transform = etree.XSLT(xslt_tree)
	DC = transform(XMLroot)		

	# 3) save to DC datastream
	DS_handle = ohandle.getDatastreamObject("DC")
	DS_handle.content = str(DC)
	derive_results = DS_handle.save()
	print "DCfromMODS result:",derive_results
	return derive_results


