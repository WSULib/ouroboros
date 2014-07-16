# utility for Batch Ingest

# celery
from cl.cl import celery

# handles
from fedoraManager2.forms import RDF_edit
from fedoraManager2.solrHandles import solr_handle
from fedoraManager2.fedoraHandles import fedora_handle
from fedoraManager2 import redisHandles
from fedoraManager2 import jobs
from fedoraManager2 import models
from fedoraManager2 import db
from fedoraManager2.forms import batchIngestForm
import fedoraManager2.actions as actions
from flask import Blueprint, render_template, abort, request, redirect

#python modules
from lxml import etree
import re

# eulfedora
import eulfedora

# create blueprint
batchIngest = Blueprint('batchIngest', __name__, template_folder='templates', static_folder="static")

# main view
@batchIngest.route('/batchIngest', methods=['POST', 'GET'])
def index():

	form = batchIngestForm()

	# get xsl transformations
	xsl_transformations = db.session.query(models.xsl_transformations)
	xsl_transformations_list = [(each.id,each.name.encode('ascii','ignore'),each.description.encode('ascii','ignore')) for each in xsl_transformations]	

	# get MODS deposits
	MODS = db.session.query(models.ingest_MODS)
	MODS_list = [(each.id,each.name.encode('ascii','ignore')) for each in MODS]	

	return render_template("batchIngest.html",form=form,xsl_transformations_list=xsl_transformations_list,MODS_list=MODS_list)


# add XSL transformation
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

	# General Message
	#############################################################################
	nav_to = "/tasks/batchIngest"
	message = "Complete"
	return render_template("genMessage.html",nav_to=nav_to,message=message)



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

	form_data = request.form		

	# grab uploaded content	
	if "MODS_id" in form_data and form_data['MODS_id'] != 'Select a MODS set':
		MODS_handle = db.session.query(models.ingest_MODS).filter_by(id=form_data['MODS_id']).first()	
		MODS = MODS_handle.MODS_content.encode('utf-8')
		MODS_upload = False
	elif 'upload' in request.files and request.files['upload'].filename != '':		
		MODS_upload = True
		MODS = request.files['upload'].read()
	elif 'MODS_content' in form_data and form_data['MODS_content'] != '':		
		MODS_upload = True
		MODS = form_data['MODS_content'].encode('utf-8')
	else:
		return "No uploaded or pasted content found, try again."
	
	# upload to DB
	if MODS_upload == True:
		MODS_injection = models.ingest_MODS(form_data['name'], form_data['xsl_trans'], MODS)	
		db.session.add(MODS_injection)
		db.session.flush()
		MODS_id = MODS_injection.id	
		db.session.commit()
	else:
		MODS_id = form_data['MODS_id']

	# get xslt transformation name
	xsl_handle = db.session.query(models.xsl_transformations).filter_by(id=form_data['xsl_trans']).first()	
	xsl_trans_name = xsl_handle.name

	# transform MODS based on provided XSL
	FOXMLs_serialized = genFOXML("provided", MODS, form_data['xsl_trans'])

	return render_template("previewIngest.html",form_data=form_data,xsl_trans_name=xsl_trans_name,MODS_id=MODS_id,FOXML_preview=FOXMLs_serialized[0])	


# ################################################################################################
# # Local Task
# ################################################################################################
# '''
# Approach here...
# have the routed function "ingestFOXML()" start the job, then run the interating ingest function ingestFOXML_worker()
# 	- good option, speedy / instant return to user
# this one runs everything through this one
# '''

# @batchIngest.route('/batchIngest/ingestFOXML', methods=['POST', 'GET'])
# def ingestFOXML():
# 	form_data = request.form

# 	# register local job
# 	new_job_package = jobs.startLocalJob()	

# 	print "Beginning bulk ingest, Job #:",new_job_package['job_num']

# 	# fire ingester
# 	ingestFOXML_worker.delay(form_data['MODS_id'], form_data['xsl_trans_id'], job_num=new_job_package['job_num'])

# 	return redirect("/userJobs")


# @celery.task()
# def ingestFOXML_worker(MODS_id, xsl_trans_id, job_num):	
# 	print MODS_id,xsl_trans_id,job_num

# 	# get FOXML
# 	FOXMLs_serialized = genFOXML("retrieve", MODS_id, xsl_trans_id)

# 	# update job info
# 	redisHandles.r_job_handle.set("job_{job_num}_est_count".format(job_num=job_num),len(FOXMLs_serialized))

	
# 	# ingest in Fedora
# 	step = 1
# 	for FOXML in FOXMLs_serialized:		
# 		jobs.jobUpdateAssignedCount(job_num)
# 		try:
# 			# ingest
# 			ingest_result = fedora_handle.ingest(FOXML)
# 			status = "SUCCESS"
# 			print "Ingested {step} / {total}".format(step=step,total=len(FOXMLs_serialized))
# 		except:
# 			status = "FAILURE"
# 			print "Error {step} / {total}".format(step=step,total=len(FOXMLs_serialized))		

# 		# update job info		
# 		redisHandles.r_job_handle.set("{job_num},{step}".format(step=step,job_num=job_num), "{status},NULL,NULL".format(status=status))

# 		if status == "SUCCESS":
# 			jobs.jobUpdateCompletedCount(job_num)


# 		# bump		
# 		step = step + 1

# 	return "Ingest finished."
# ################################################################################################


################################################################################################
# Action Tasks ( utilitizes taskWrapper() )
################################################################################################
'''
Different approach here...
*anticpated problem: for very large lists of FOXML, not having a similar celeryTaskFactory() will cause this to delay.
'''

@batchIngest.route('/batchIngest/ingestFOXML', methods=['POST', 'GET'])
def ingestFOXML():
	form_data = request.form

	# register local job
	job_package = jobs.startLocalJob()	
	job_num = job_package['job_num']

	print "Beginning bulk ingest, Job #:",job_num

	# get FOXML
	FOXMLs_serialized = genFOXML("retrieve", form_data['MODS_id'], form_data['xsl_trans_id'])

	# update job info
	redisHandles.r_job_handle.set("job_{job_num}_est_count".format(job_num=job_num),len(FOXMLs_serialized))

	job_package['task_name'] = "ingestFOXML_worker"

	# ingest in Fedora
	step = 1
	for FOXML in FOXMLs_serialized:		

		job_package['PID'] = "N/A"
		job_package['step'] = step		
		job_package['FOXML'] = FOXML

		# fire ingester
		result = actions.actions.taskWrapper.delay(job_package)

		task_id = result.id		
		
		redisHandles.r_job_handle.set("{job_num},{step}".format(step=step,job_num=job_num), "FIRED,{task_id},{PID}".format(task_id=task_id,PID=job_package['PID']))
			
		# update incrementer for total assigned
		jobs.jobUpdateAssignedCount(job_num)

		# bump step
		step += 1

	return redirect("/userJobs")



def ingestFOXML_worker(job_package):	

	FOXML = job_package['FOXML']	
	ingest_result = fedora_handle.ingest(FOXML)
	return ingest_result	

	
################################################################################################


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
	



















