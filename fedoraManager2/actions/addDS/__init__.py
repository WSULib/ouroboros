# TASK: addDS - Add Datastream

# handles
from fedoraManager2.fedoraHandles import fedora_handle
from flask import Blueprint, render_template, abort
from wtforms import Form, BooleanField, StringField, SelectField, TextAreaField, FileField, validators, fields
import eulfedora


addDS = Blueprint('addDS', __name__, template_folder='templates', static_folder="static")


@addDS.route('/addDS')
def index():

	class addDSForm(Form):
		# using params verbatim from Fedora documentation
		dsID = StringField('Datastream ID:')
		altIDs = StringField('Alternate Datastream ID:')		
		dsLabel = StringField('Datastream Label:')
		MIMEType = StringField('MIME-Type:')
		dsLocation = StringField('Location (note: will trump content below):')
		controlGroup = SelectField('Control Group:', choices=[('M', 'Managed Content'), ('X', 'Inline XML'), ('R', 'Redirect'), ('E', 'External Referenced')])	
		content = TextAreaField('Paste Content (usually XML, and trumps file upload)')
		upload = FileField('Upload Content')

	form = addDSForm()
	
	return render_template("addDS_index.html",form=form)



def addDS_worker(job_package):
	'''
	Improvements:
		- automatically detect MIMEType if file uploaded
	'''

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
	if form_data['content'] != '':
		newDS.content = form_data['content']

	# save constructed object
	newDS.save()


	form_data = job_package['form_data']	
	print form_data	
	
	
	