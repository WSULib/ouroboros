# utility for Batch Ingest

# celery
from cl.cl import celery

# handles
from fedoraManager2.forms import RDF_edit
from fedoraManager2.solrHandles import solr_handle
from fedoraManager2.fedoraHandles import fedora_handle
from fedoraManager2 import redisHandles, jobs, models, db, forms
import fedoraManager2.actions as actions
from flask import Blueprint, render_template, abort, request, redirect, session

#python modules
from lxml import etree
import re

# eulfedora
import eulfedora

# create blueprint
bagIngest = Blueprint('bagIngest', __name__, template_folder='templates', static_folder="static")

# main view
@bagIngest.route('/bagIngest', methods=['POST', 'GET'])
def index():

	form = forms.bagIngestForm()	

	return render_template("bagIngestIndex.html")



	



















