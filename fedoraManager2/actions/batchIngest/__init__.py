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
	print form_data.keys()	

	# grab uploaded content	
	if 'upload' in request.files and request.files['upload'].filename != '':		
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
		if 'upload' in request.files and request.files['upload'].filename != '':		
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

	'''
	1) upload MODS file to MySQL?  This way, the actual ingest process can work off that, and not shuffling around form data
	2) what preview?  mock FOXML file, by extracting one <mods:mods> element?
		- preview and ingest *could* share a function to generate the FOXML		
	'''

	form_data = request.form	

	# grab uploaded content	
	if 'upload' in request.files and request.files['upload'].filename != '':		
		MODS = request.files['upload'].read()
	elif 'MODS_content' in form_data:		
		MODS = form_data['MODS_content'].encode('utf-8')
	else:
		return "No uploaded or pasted content found, try again."
	
	# upload to DB
	MODS_injection = models.ingest_MODS(form_data['name'], form_data['xsl_trans'], MODS)	
	db.session.add(MODS_injection)
	db.session.flush()
	MODS_id = MODS_injection.id	
	db.session.commit()	

	# get xslt transformation name
	xsl_handle = db.session.query(models.xsl_transformations).filter_by(id=form_data['xsl_trans']).first()	
	xsl_trans_name = xsl_handle.name

	# transform MODS based on provided XSL
	FOXMLs_serialized = genFOXML("provided", MODS, form_data['xsl_trans'])

	return render_template("previewIngest.html",form_data=form_data,xsl_trans_name=xsl_trans_name,MODS_id=MODS_id,FOXML_preview=FOXMLs_serialized[0])	




@batchIngest.route('/batchIngest/ingestFOXML', methods=['POST', 'GET'])
def ingestFOXML():

	form_data = request.form
	print form_data

	

	
def ingestFOXML_worker(job_package):		

	form_data = job_package['form_data']
	print form_data

	# get FOXML
	FOXMLs_serialized = genFOXML("retrieve", form_data['MODS_id'], form_data['xsl_trans_id'])
	
	# ingest in Fedora
	for FOXML in FOXMLs_serialized:
		print fedora_handle.ingest(FOXML)



def genFOXML(MODS_type, MODS, xsl_trans):
	'''
	Return dictionary or list with FOXML for each object in MODS file, where key is object ID?
	Excpecting
		- MODS collection <mods:modsCollection> as string, properly formed XML
		- xsl_transform key, integer, where this function can grab XSL from the database
	'''

	FOXML_package = {}

	# get MODS
	if MODS_type == "provided": 
		XMLroot = etree.fromstring(MODS)
	if MODS_type == "retrieve":
		MODS_handle = db.session.query(models.ingest_MODS).filter_by(id=MODS).first()		
		XMLroot =etree.fromstring(MODS_handle.MODS_content.encode('utf-8'))

	# get xslt handle from DB
	xsl_handle = db.session.query(models.xsl_transformations).filter_by(id=xsl_trans).first()	
	xslt_tree = etree.fromstring(xsl_handle.xsl_content)

	# transform, creating new XML doc with <FOXMLcollection> root
	transform = etree.XSLT(xslt_tree)
	FOXML = transform(XMLroot)
	FOXML_string = etree.tostring(FOXML)

	# parse into list
	FOXMLroot = etree.fromstring(FOXML_string)
	FOXMLs = FOXMLroot.findall('{info:fedora/fedora-system:def/foxml#}digitalObject')
	FOXMLs_serialized = [etree.tostring(FOXML) for FOXML in FOXMLs]
	
	return FOXMLs_serialized	
	



















