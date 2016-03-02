# -*- coding: utf-8 -*-
# TASK: import / export MODS batch update

# celery
from cl.cl import celery

# handles
from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager.forms import importMODS
from WSUDOR_Manager import utilities, jobs, redisHandles, jobs, models, db, actions
from flask import Blueprint, render_template, abort, session, make_response, request, redirect
import eulfedora

from lxml import etree, objectify
import requests
import uuid
import os


MODSexport = Blueprint('MODSexport', __name__, template_folder='templates', static_folder="static")


@MODSexport.route('/MODSexport')
@utilities.objects_needed
def index():

	
	return render_template("MODSexport_index.html")


@MODSexport.route('/MODSexport/export')
@utilities.objects_needed
def MODSexport_export():

	# get username
	username = session['username']

	#register namespaces
	etree.register_namespace('mods', 'mods:http://www.loc.gov/mods/v3')

	# collect MODS records for selected objects	
	PIDs = jobs.getSelPIDs()
	with open('/tmp/Ouroboros/%s_MODS_concat.xml' % (username), 'w') as outfile:

		# write header
		outfile.write('<?xml version="1.0" encoding="UTF-8"?><mods:modsCollection xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:mods="http://www.loc.gov/mods/v3" xsi:schemaLocation="http://www.loc.gov/mods/v3 http://www.loc.gov/standards/mods/v3/mods-3-4.xsd">\n')

		for PID in PIDs:

			# get MODS ds
			obj_ohandle = fedora_handle.get_object(PID)					
			ds_handle = obj_ohandle.getDatastreamObject('MODS')
			

			'''
			Little bit of complexity here:
			For this kind of MODS in & out, we need the current PID associated with the file on the way out.
			Writing this to the <mods:extension> field, creating if not present.
			'''

			# does <PID> element already exist?
			PID_check = ds_handle.content.node.xpath('//mods:extension/PID',namespaces=ds_handle.content.node.nsmap)
			# if not, continue with checks
			if len(PID_check) == 0:

				# check for <mods:extension>, if not present add
				extension_check = ds_handle.content.node.xpath('//mods:extension',namespaces=ds_handle.content.node.nsmap)
				
				# if absent, create with <PID> subelement
				if len(extension_check) == 0:
					#serialize and replace
					MODS_content = ds_handle.content.serialize()				
					MODS_content = MODS_content.replace("</mods:mods>","<mods:extension><PID>{PID}</PID></mods:extension></mods:mods>".format(PID=PID))
				
				# <mods:extension> present, but no PID subelement, create
				else:
					PID_elem = etree.SubElement(extension_check[0],"PID")
					PID_elem.text = PID
					#serialize
					MODS_content = ds_handle.content.serialize()

			# skip <PID> element creation, just serialize
			else:
				MODS_content = ds_handle.content.serialize()

			# write to file
			outfile.write(MODS_content)

		# close MODS collection
		outfile.write('\n</mods:modsCollection>')
	
	# close file
	outfile.close()

	# open file from tmp and return as download
	fhand = open('/tmp/Ouroboros/%s_MODS_concat.xml' % (username), 'r')
	response = make_response(fhand.read())
	response.headers["Content-Disposition"] = "attachment; filename=MODS_export.xml"
	return response



@MODSexport.route('/MODSexport/import_form')
def MODSexport_import():

	# receive <mods:modsCollection>, parse, update associated MODS records
	form = importMODS()	
	return render_template("MODSexport_import.html", form=form)


@MODSexport.route('/MODSexport/import_fire', methods=['POST','GET'])
def import_fire():	
	# get new job num
	job_num = jobs.jobStart()

	# get username
	username = session['username']	

	# prepare job_package for boutique celery wrapper
	job_package = {
		'job_num':job_num,
		'task_name':"importMODS_worker",
		'form_data':request.form
	}	

	# pass along binary uploaded data if included in job task
	if 'upload' in request.files and request.files['upload'].filename != '':
		job_package['upload_data'] = request.files['upload'].read()

	# job celery_task_id
	celery_task_id = celeryTaskFactoryImportMODS.delay(job_num,job_package)		 

	# send job to user_jobs SQL table
	db.session.add(models.user_jobs(job_num, username, celery_task_id, "init", "importMODS"))	
	db.session.commit()		

	print "Started job #",job_num,"Celery task #",celery_task_id
	return redirect("/userJobs")


@celery.task(name="celeryTaskFactoryImportMODS")
def celeryTaskFactoryImportMODS(job_num,job_package):

	'''
	Problem - too big to send the MODS XML to Redis.  Need to stick it in MySQL, or text file.
	Write to temp file.  Case closed. 
	'''
	
	# reconstitute
	form_data = job_package['form_data']
	job_num = job_package['job_num']

	# get mods:collection 
	if 'upload_data' in job_package:		
		MODS_collection = job_package['upload_data']
		job_package['upload_data'] = False #scrub data
	elif form_data['content'] != '':
		MODS_collection = form_data['content'] 
		form_data['content'] = False #scrub data

	# shunt each MODS record to list
	MODS_collection = unicode(MODS_collection, 'utf-8')
	XMLroot = etree.fromstring(MODS_collection.encode('utf-8'))	
	MODS_list = XMLroot.findall('{http://www.loc.gov/mods/v3}mods')	

	# update job info
	redisHandles.r_job_handle.set("job_%s_est_count" % (job_num), len(MODS_list))

	# ingest in Fedora
	step = 1
	for MODS_elem in MODS_list:

		# read <mods:extension><PID>, pass this as PID
		PID_search = MODS_elem.findall("{http://www.loc.gov/mods/v3}extension/PID")
		if len(PID_search) == 0:
			print "Could not find PID, skipping"
			continue
		else:
			PID = PID_search[0].text

		# write MODS to temp file
		temp_filename = "/tmp/Ouroboros/"+str(uuid.uuid4())+".xml"
		fhand = open(temp_filename,'w')
		fhand.write(etree.tostring(MODS_elem))
		fhand.close()

		job_package['PID'] = PID
		job_package['step'] = step		
		job_package['MODS'] = temp_filename

		# fire ingester
		result = actions.actions.taskWrapper.delay(job_package)

		task_id = result.id		
			
		# update incrementer for total assigned
		jobs.jobUpdateAssignedCount(job_num)

		# bump step
		step += 1

	
def genMODS(MODS):	

	XMLroot = etree.fromstring(MODS.encode('utf-8'))	
	single_elem_list = XMLroot.findall('{http://www.loc.gov/mods/v3}mods')

	MODS_list = [etree.tostring(MODS) for MODS in single_elem_list]
	return MODS_list


def importMODS_worker(job_package):	
	'''
	Receive job_package, which contains PID, update MODS
	'''	

	PID = job_package['PID']
	MODS = job_package['MODS']	
	print "Updating MODS for %s" % (PID)

	# open temp MODS file, read, delete
	fhand = open(MODS,'r')
	MODS_string = fhand.read()
	fhand.close()
	os.system("rm %s" % (MODS))

	obj_handle = fedora_handle.get_object(PID)
	ds_handle = obj_handle.getDatastreamObject("MODS")
	ds_handle.content = MODS_string
	return ds_handle.save()





























