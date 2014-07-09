# utility for Batch Ingest

# handles
from fedoraManager2.forms import RDF_edit
from fedoraManager2.solrHandles import solr_handle
from fedoraManager2.fedoraHandles import fedora_handle
from fedoraManager2.jobs import getSelPIDs
from fedoraManager2 import models
from fedoraManager2 import db
from fedoraManager2.forms import batchIngestForm
from flask import Blueprint, render_template, abort, request

#python modules
from lxml import etree
import re

# eulfedora
import eulfedora


batchIngest = Blueprint('batchIngest', __name__, template_folder='templates', static_folder="static")


'''
- Upon upload of <mods:collection> file...
	1) select XSL transformation to use 
	2) break on <mods:mods>, grab XML
		- run sub-ingest, celery function?
	3) transform to FOXML
	4) index.
'''


@batchIngest.route('/batchIngest', methods=['POST', 'GET'])
def index():

	form = batchIngestForm()

	# get xsl transformations
	xsl_transformations = db.session.query(models.xsl_transformations)
	xsl_transformations_list = [(each.id,each.name.encode('ascii','ignore'),each.description.encode('ascii','ignore')) for each in xsl_transformations]	

	return render_template("batchIngest.html",form=form,xsl_transformations_list=xsl_transformations_list)


@batchIngest.route('/batchIngest/addXSLTrans', methods=['POST', 'GET'])
def addXSL():
	print "Adding XSL transformation to MySQL"

	form_data = request.form
	print form_data

	print request.files

	# grab uploaded content	
	if request.files['upload'].filename != '':		
		xsl_content = request.files['upload'].read()
	elif 'content' in form_data:		
		xsl_content = form_data['content'].encode('utf-8')
	else:
		return "No uploaded or pasted content found, try again."	
	
	# upload to DB	
	db.session.add(models.xsl_transformations(form_data['name'], form_data['description'], xsl_content ))	
	db.session.commit()	

	return "All Done."



@batchIngest.route('/batchIngest/editXSLTrans/<action_type>', methods=['POST', 'GET'])
def editXSL(action_type):
	print "Editing XSL transformation from MySQL"	

	# submit changes
	if action_type == "modify":				
		form_data = request.form
		xsl_trans_id = form_data['id']		

		# grab uploaded content	
		if request.files['upload'].filename != '':		
			xsl_content = request.files['upload'].read()
		elif 'content' in form_data:		
			xsl_content = form_data['content'].encode('utf-8')
		else:
			return "No uploaded or pasted content found, try again."
		

		# upload to DB	
		xsl_transform = models.xsl_transformations.query.filter_by(id=xsl_trans_id).first()
		xsl_transform.name = form_data['name']
		xsl_transform.description = form_data['description']
		xsl_transform.xsl_content = xsl_content
		db.session.commit()

		return render_template("editXSLTrans.html",form_data=form_data)
	
	# retrive to edit
	else:
		print "Retrieving..."
		form = batchIngestForm()
		form_data = request.form
		xsl_trans_id = form_data['xsl_trans']
		# get xsl transformation
		xsl_transform = models.xsl_transformations.query.filter_by(id=xsl_trans_id).first()
		return render_template("editXSLTrans.html",form=form, xsl_transform=xsl_transform)


@batchIngest.route('/batchIngest/previewIngest', methods=['POST', 'GET'])
def previewIngest():

	form_data = request.form
	print form_data

	'''
	1) upload MODS file to MySQL?  This way, the actual ingest process can work off that, and not shuffling around form data
	2) what preview?  mock FOXML file, by extracting one <mods:mods> element?
		- preview and ingest *could* share a function to generate the FOXML		
	'''

	return render_template("previewIngest.html",form_data=form_data)	




@batchIngest.route('/batchIngest/ingestFOXML', methods=['POST', 'GET'])
def ingestFOXML():

	form_data = request.form
	print form_data

	'''
	
	1) read MODS file
	2) for each <mods:mods>, run XSL transform (might require little tweaking), save results to variable
	3) ingest into  Fedora 
		
	'''

	return "Uploading"
	


def batchIngest_worker(job_package):	
	pass






















