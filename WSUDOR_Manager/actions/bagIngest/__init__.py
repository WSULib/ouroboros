# utility for Bag Ingest

# celery
from cl.cl import celery

# handles
from WSUDOR_Manager.forms import RDF_edit
from WSUDOR_Manager.solrHandles import solr_handle
from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager import redisHandles, jobs, models, db, forms
import WSUDOR_Manager.actions as actions
import WSUDOR_ContentTypes

from flask import Blueprint, render_template, abort, request, redirect, session

# Content Types
# from WSUDOR_ContentTypes.WSUDOR_Object import WSUDOR_Object

#python modules
from lxml import etree
import re
import json

# eulfedora
import eulfedora

# import bagit
import bagit

# create blueprint
bagIngest = Blueprint('bagIngest', __name__, template_folder='templates', static_folder="static")


# main view
@bagIngest.route('/bagIngest', methods=['POST', 'GET'])
def index():

	# form = forms.bagIngestForm()	

	return render_template("bagIngestIndex.html")


# singleBag view
@bagIngest.route('/bagIngest/singleBag', methods=['POST', 'GET'])
def singleBag_index():

	if request.args.get('bag_dir'):		
		singleBag_ingest_worker(request)

	return render_template("singleBagIndex.html")


# ingest singleBag
def singleBag_ingest_worker(request):

	print request.args		

	# load bag_handle
	bag_dir = request.args.get("bag_dir")
	print "Working on:",bag_dir
	bag_handle = WSUDOR_ContentTypes.WSUDOR_Object(object_type="bag",payload=bag_dir)
	
	# validate bag for WSUDOR ingest	
	valid_results = bag_handle.validIngestBag()
	if valid_results['verdict'] != True:
		print "Bag is not valid for the following reasons, aborting."
		print valid_results
		return False


	# ingest bag
	ingest_bag = bag_handle.ingestBag()
	return ingest_bag


# ingest singleBag
def collectionBag_ingest(request):	

	pass












