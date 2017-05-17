# TASK: purgeDS - Purge Datastream

# handles
from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager.forms import purgeDSForm
from WSUDOR_Manager.jobs import getSelPIDs
from WSUDOR_Manager import utilities, roles, logging
from flask import Blueprint, render_template, request


purgeDS = Blueprint('purgeDS', __name__, template_folder='templates', static_folder="static")


@purgeDS.route('/purgeDS', methods=['POST', 'GET'])
@utilities.objects_needed
@roles.auth(['admin'])
def index():

	# get PID to examine, if noted
	if request.args.get("PIDnum") != None:
		PIDnum = int(request.args.get("PIDnum"))		
	else:
		PIDnum = 0

	# get PIDs	
	PIDs = getSelPIDs()	
	logging.debug(PIDs[PIDnum])

	obj_ohandle = fedora_handle.get_object(PIDs[PIDnum])		
	obj_ohandle = obj_ohandle.ds_list
	dsIDs = []
	for (name, loc) in obj_ohandle.items():
		dsIDs.extend([name])
	logging.debug(dsIDs)

	form = purgeDSForm()	
	return render_template("purgeDS.html",form=form,PID=PIDs[PIDnum],dsIDs=dsIDs,PIDnum=PIDnum)


@roles.auth(['admin'], is_celery=True)
def purgeDS_worker(job_package):

	logging.debug(job_package)
	form_data = job_package['form_data']	
	logging.debug(form_data)

	PID = job_package['PID']		
	logging.debug(PID)

	return fedora_handle.api.purgeDatastream(PID, form_data['dsID'], form_data['logMessage'], form_data['startDT'], form_data['endDT'], form_data['force'])