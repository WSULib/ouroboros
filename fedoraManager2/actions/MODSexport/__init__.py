# TASK: addDS - Add Datastream

# handles
from fedoraManager2.fedoraHandles import fedora_handle
from fedoraManager2.forms import importMODS
from fedoraManager2 import utilities, jobs
from flask import Blueprint, render_template, abort, session, make_response
import eulfedora

from lxml import etree, objectify


MODSexport = Blueprint('MODSexport', __name__, template_folder='templates', static_folder="static")

'''
QUESTION
Currently iterating through currentl selected PIDs, grabbing associated MODS record from uploaded content.
Pro: 
	- in-line with current system
	- simpler
Con: 
	- probably much slower
	- requires selecting same PIDs that are found in MODS record
'''


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
	with open('/tmp/Ouroboros/{username}_MODS_concat.xml'.format(username=username), 'w') as outfile:

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
	fhand = open('/tmp/Ouroboros/{username}_MODS_concat.xml'.format(username=username), 'r')
	response = make_response(fhand.read())
	response.headers["Content-Disposition"] = "attachment; filename=MODS_export.xml"
	return response


@MODSexport.route('/MODSexport/import')
@utilities.objects_needed
def MODSexport_import():

	# receive <mods:modsCollection>, parse, update associated MODS records
	form = importMODS()
	
	return render_template("MODSexport_import.html", form=form)


def MODSexport_worker(job_package):	

	form_data = job_package['form_data']	
	print form_data
	
	PID = job_package['PID']

	# open handle		
	obj_ohandle = fedora_handle.get_object(PID)

	# initialized DS object and rewrite MODS
	ds_handle = obj_ohandle.getDatastreamObject('MODS')	

	# get mods:collection 
	if 'upload_data' in job_package:		
		MODS_collection = job_package['upload_data']
	elif form_data['content'] != '':
		MODS_collection = form_data['content']		

	# extract MODS for current PID	
	MODS_root = etree.fromstring(MODS_collection)
	xpath_string = '//PID[text()="{PID}"]'.format(PID=PID)
	print xpath_string
	PID_find = MODS_root.xpath(xpath_string,namespaces=MODS_root.nsmap)
	cPID = PID_find[0]
	cMODS = cPID.getparent().getparent()
	print cMODS
	MODS_string = etree.tostring(cMODS)

	# update content
	ds_handle.content = MODS_string	

	# save constructed object
	return ds_handle.save()

































