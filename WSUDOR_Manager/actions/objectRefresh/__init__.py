# utility for Bag Ingest

# celery
from WSUDOR_Manager import celery

# handles
from WSUDOR_Manager.forms import RDF_edit
from WSUDOR_Manager.solrHandles import solr_handle
from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager import redisHandles, jobs, models, db, forms, roles
import WSUDOR_Manager.actions as actions
import WSUDOR_ContentTypes

import flask
from flask import Blueprint, render_template, abort, request, redirect, session

#python modules
from lxml import etree
import re
import json
import os
import tarfile
import uuid
import time

# eulfedora
import eulfedora

# create blueprint
objectRefresh = Blueprint('objectRefresh', __name__, template_folder='templates', static_folder="static")


# main view
@objectRefresh.route('/objectRefresh/<PID>', methods=['POST', 'GET'])
@roles.auth(['admin','metadata'])
def index(PID):

	'''
	Runs uber object method self.objectRefresh().
	Does this need to be in Celery?
	'''

	obj_handle = WSUDOR_ContentTypes.WSUDOR_Object(PID)
	
	# run self.objectRefresh()
	stime = time.time()

	try:
		obj_handle.objectRefresh()
		return_dict = {
			'pid':PID,
			'result':True
		}
	except:
		return_dict = {
			'pid':PID,
			'result':False
		}

	return_dict['time_elapse'] = time.time() - stime
	return flask.jsonify(**return_dict)
