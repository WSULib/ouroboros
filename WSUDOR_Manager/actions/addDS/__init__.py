# TASK: addDS - Add Datastream

# handles
from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager.forms import addDSForm
from WSUDOR_Manager import utilities, roles
from flask import Blueprint, render_template, abort
from flask.ext.login import login_required
import eulfedora


addDS = Blueprint('addDS', __name__, template_folder='templates', static_folder="static")


@addDS.route('/addDS')
@utilities.objects_needed
@roles.auth(['admin','metadata'])
def index():

	form = addDSForm()	
	return render_template("addDS_index.html",form=form)


@roles.auth(['admin','metadata'], is_celery=True)
def addDS_worker(job_package):
	
	form_data = job_package['form_data']	
	print form_data
	
	PID = job_package['PID']		
	obj_ohandle = fedora_handle.get_object(PID)

	# initialized DS object
	newDS = eulfedora.models.DatastreamObject(obj_ohandle, form_data['dsID'], form_data['dsLabel'], control_group=form_data['controlGroup'])	

	# construct DS object
	if form_data['MIMEType'] != '':		
		newDS.mimetype = form_data['MIMEType']	
	if form_data['dsLocation'] != '':
		newDS.ds_location = form_data['dsLocation']	

	# content
	if 'upload_data' in job_package:
		with open(job_package['upload_data'],'r') as fhand:
			newDS.content = fhand.read()
	elif form_data['content'] != '':
		newDS.content = form_data['content']	

	# save constructed object
	return newDS.save()
	
	