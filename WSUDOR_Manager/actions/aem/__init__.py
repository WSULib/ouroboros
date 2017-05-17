# utility for Bag Ingest

# celery
from WSUDOR_Manager import celery, utilities, fedoraHandles

# handles
from WSUDOR_Manager.forms import RDF_edit
from WSUDOR_Manager.solrHandles import solr_handle
from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager import redisHandles, jobs, models, db, forms, models, roles, logging
import WSUDOR_Manager.actions as actions
import WSUDOR_ContentTypes
try:
	import ouroboros_assets
except:
	logging.debug("could not load git submodule 'ouroboros_assets'")
import localConfig

from flask import Blueprint, render_template, abort, request, redirect, session, jsonify, Response

#python modules
from lxml import etree
import re
import json
import os
import tarfile
import uuid
from string import upper
import xmltodict
import requests
import time
import traceback
import subprocess

# sql or
from sqlalchemy import or_

# eulfedora
import eulfedora

# import bagit
import bagit

# flask-SQLalchemy-datatables
from datatables import ColumnDT, DataTables

# mets-reader-writer (metsrw)
import metsrw

# create blueprint
aem = Blueprint('aem', __name__, template_folder='templates', static_folder="static")



#################################################################################
# Routes
#################################################################################

# main view
@aem.route('/aem', methods=['POST', 'GET'])
@roles.auth(['admin','metadata'])
def index():	

	return render_template("aem.html")





























