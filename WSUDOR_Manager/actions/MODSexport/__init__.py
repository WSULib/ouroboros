# -*- coding: utf-8 -*-
# TASK: import / export MODS batch update

# celery
from WSUDOR_Manager import celery

# handles
from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager.forms import importMODS
from WSUDOR_Manager import utilities, jobs, redisHandles, jobs, models, db, actions, roles
from flask import Blueprint, render_template, abort, session, make_response, request, redirect
from flask.ext.login import login_required
import eulfedora

from lxml import etree, objectify
import requests
import uuid
import os
import time


MODSexport = Blueprint('MODSexport', __name__, template_folder='templates', static_folder="static")


@MODSexport.route('/MODSexport')
@utilities.objects_needed
@login_required
@roles.auth(['admin','metadata'])
def index():
	
	return render_template("MODSexport_index.html")


@MODSexport.route('/MODSexport/export')
@utilities.objects_needed
@login_required
@roles.auth(['admin','metadata'])
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

			Update: This will be forced.  Without the PID, records will not be associated.  Critical for reingest.
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
					MODS_content = MODS_content.replace("</mods:mods>","<mods:extension><PID>%s</PID></mods:extension></mods:mods>" % PID)
				
				# <mods:extension> present, but no PID subelement, create
				else:
					PID_elem = etree.SubElement(extension_check[0],"PID")
					PID_elem.text = PID
					#serialize
					MODS_content = ds_handle.content.serialize()

			# overwrite with PID
			else:
				PID_element = PID_check[0]
				PID_element.text = PID
				#serialize
				MODS_content = ds_handle.content.serialize()


			# # OLD
			# # if not, continue with checks
			# if len(PID_check) == 0:

			# 	# check for <mods:extension>, if not present add
			# 	extension_check = ds_handle.content.node.xpath('//mods:extension',namespaces=ds_handle.content.node.nsmap)
				
			# 	# if absent, create with <PID> subelement
			# 	if len(extension_check) == 0:
			# 		#serialize and replace
			# 		MODS_content = ds_handle.content.serialize()				
			# 		MODS_content = MODS_content.replace("</mods:mods>","<mods:extension><PID>%s</PID></mods:extension></mods:mods>" % PID)
				
			# 	# <mods:extension> present, but no PID subelement, create
			# 	else:
			# 		PID_elem = etree.SubElement(extension_check[0],"PID")
			# 		PID_elem.text = PID
			# 		#serialize
			# 		MODS_content = ds_handle.content.serialize()

			# # skip <PID> element creation, just serialize
			# else:
			# 	MODS_content = ds_handle.content.serialize()

			
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



# IMPORT
@MODSexport.route('/MODSexport/import_form')
@login_required
@roles.auth(['admin','metadata'])
def MODSexport_import():

	# receive <mods:modsCollection>, parse, update associated MODS records
	form = importMODS()	
	return render_template("MODSexport_import.html", form=form)


@celery.task(name="MODSimport_factory")
def MODSimport_factory(job_package):

	print "FIRING MODSimport_factory"

	# get form data
	form_data = job_package['form_data']	

	# set new task_name, for the worker below
	job_package['custom_task_name'] = 'MODSimport_worker'	

	# get mods:collection 
	if 'upload_data' in job_package:
		with open(job_package['upload_data'], 'r') as fhand:		
			MODS_collection = fhand.read()
	elif form_data['content'] != '':
		MODS_collection = form_data['content'] 

	# shunt each MODS record to list
	MODS_collection = unicode(MODS_collection, 'utf-8')
	XMLroot = etree.fromstring(MODS_collection.encode('utf-8'))	
	MODS_list = XMLroot.findall('{http://www.loc.gov/mods/v3}mods')
	print MODS_list

	# update job info
	redisHandles.r_job_handle.set("job_%s_est_count" % (job_package['job_num']), len(MODS_list))

	# ingest in Fedora
	step = 1
	for MODS_elem in MODS_list:

		print "Loading %s / %s" % (step, len(MODS_list))

		# read <mods:extension><PID>, pass this as PID
		PID_search = MODS_elem.findall("{http://www.loc.gov/mods/v3}extension/PID")
		if len(PID_search) == 0:
			print "Could not find PID, skipping"
			# bump step
			step += 1
			continue
		else:
			PID = PID_search[0].text
			print "FOUND THE PID:",PID

		# write MODS to temp file
		temp_filename = "/tmp/Ouroboros/"+str(uuid.uuid4())+".xml"
		fhand = open(temp_filename,'w')
		fhand.write(etree.tostring(MODS_elem))
		fhand.close()

		job_package['PID'] = PID
		job_package['step'] = step		
		job_package['MODS'] = temp_filename
		
		# fire task via custom_loop_taskWrapper			
		result = actions.actions.custom_loop_taskWrapper.apply_async(kwargs={'job_package':job_package}, queue=job_package['username'])
		task_id = result.id

		# Set handle in Redis
		redisHandles.r_job_handle.set("%s" % (task_id), "FIRED,%s" % (PID))
			
		# update incrementer for total assigned
		jobs.jobUpdateAssignedCount(job_package['job_num'])

		# bump step
		step += 1

	print "Finished firing MODS import workers"


@roles.auth(['admin','metadata'], is_celery=True)
def MODSimport_worker(job_package):	
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






























