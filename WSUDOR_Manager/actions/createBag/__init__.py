# utility for Bag Ingest

# celery
from WSUDOR_Manager import celery

# handles
from WSUDOR_Manager.solrHandles import solr_handle
from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager import redisHandles, jobs, models, db, forms
import WSUDOR_Manager.actions as actions
import WSUDOR_ContentTypes
from WSUDOR_Manager.models import ObjMeta
import WSUDOR_Manager.forms as forms


from flask import Blueprint, render_template, abort, request, redirect, session

#python modules
from lxml import etree
import re
import json
import os
import tarfile
import uuid

# eulfedora
import eulfedora

# import bagit
import bagit

# create blueprint
createBag = Blueprint('createBag', __name__, template_folder='templates', static_folder="static")




## WSUDOR_WSUebook ########################################################################################
# main view
@createBag.route('/createBag/WSUDOR_WSUebook', methods=['POST', 'GET'])
def index():

	form = forms.createBagForm_WSUebook()
	return render_template("createBag_WSUDOR_WSUebook.html",form=form)


# singleBag worker
@createBag.route('/createBag/WSUDOR_WSUebook/create', methods=['POST', 'GET'])
def createBag_create():	

	def abort(msg):
		# rollback changes?
		return msg


	# get username
	username = session['username']			
	print request.form
	form_results = request.form

	
	# make output dir
	try:
		print "Making directory..."
		# os.mkdir(form_results['outputLocation'])
	except:
		return abort("Directory already exists or could permissions restrict")


	# instantiate objMeta instance
	handle = ObjMeta(**{
			"id" : form_results['objID'],
			"label" : form_results['objLabel']			
		})

	# get content type
	content_rels = form_results['hasContentModel']
	# this is the price of WSUDOR_ContentTypes and Fedora CM:* content types...
	wct = "WSUDOR_"+json.loads(content_rels)['object'].split(":")[-1]
	print "WSUDOR Content Type:",wct
	handle.content_type = wct

	

	# debug
	print handle.toJSON()
	return handle.displayJSONWeb()


	



