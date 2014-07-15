# TASK: addDS - Add Datastream

# handles
from fedoraManager2.fedoraHandles import fedora_handle
from fedoraManager2.forms import addDSForm
from flask import Blueprint, render_template, abort
import eulfedora


addDS = Blueprint('addDS', __name__, template_folder='templates', static_folder="static")


@addDS.route('/addDS')
def index():

	form = addDSForm()	
	return render_template("addDS_index.html",form=form)



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
		newDS.content = job_package['upload_data']
	elif form_data['content'] != '':
		newDS.content = form_data['content']

	print newDS.content

	# save constructed object
	newDS.save()


	form_data = job_package['form_data']	
	print form_data	
	
	
	