# TASK: purgeDS - Purge Datastream

# handles
from fedoraManager2.fedoraHandles import fedora_handle
from fedoraManager2.forms import purgeDSForm
from fedoraManager2.jobs import getSelPIDs
from flask import Blueprint, render_template, request


purgeDS = Blueprint('purgeDS', __name__, template_folder='templates', static_folder="static")


@purgeDS.route('/purgeDS', methods=['POST', 'GET'])
def index():

	# get PID to examine, if noted
	if request.args.get("PIDnum") != None:
		PIDnum = int(request.args.get("PIDnum"))		
	else:
		PIDnum = 0

	# get PIDs	
	PIDs = getSelPIDs()	
	print PIDs[PIDnum]

	# obj_ohandle = fedora_handle.get_object("wayne:Fake02b")
	obj_ohandle = fedora_handle.get_object(PIDs[PIDnum])		
	obj_ohandle = obj_ohandle.ds_list
	dsIDs = []
	for (name, loc) in obj_ohandle.items():
		dsIDs.extend([name])
	print dsIDs

	form = purgeDSForm()	
	return render_template("purgeDS.html",form=form,PID=PIDs[PIDnum],dsIDs=dsIDs,PIDnum=PIDnum)



def purgeDS_worker(job_package):
	# Note: need to check if it works when you remove all the form data below that is empty
	# Note: also see what the form_data and PID print out to
	form_data = job_package['form_data']	
	print form_data

	PID = job_package['PID']		
	print PID
	# obj_ohandle = fedora_handle.get_object(PID)
	# fedora_handle.api.purgeDatastream(obj_ohandle, form_data['dsID'], form_data['logMessage'], form_data['startDT'], form['endDT'], form['force'])

	# # # initialized DS object
	# # newDS = eulfedora.models.DatastreamObject(obj_ohandle, form_data['dsID'], form_data['dsLabel'], control_group=form_data['controlGroup'])	

	# form_data = job_package['form_data']	
	# print form_data	