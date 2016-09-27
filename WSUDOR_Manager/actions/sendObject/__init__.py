# TASK: sendObject - Purge Datastream

# handles
from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager import utilities
import WSUDOR_ContentTypes
import localConfig
from flask import Blueprint, render_template, request


sendObject = Blueprint('sendObject', __name__, template_folder='templates', static_folder="static")


@sendObject.route('/sendObject', methods=['POST', 'GET'])
@utilities.objects_needed
@roles.auth(['admin'])
def index():

	return render_template("sendObject.html", REMOTE_REPOSITORIES=localConfig.REMOTE_REPOSITORIES)


@roles.auth(['admin'], is_celery=True)
def sendObject_worker(job_package):

	# open handle
	obj_handle = WSUDOR_ContentTypes.WSUDOR_Object(job_package['PID'])	

	# get params
	# set destination repo
	dest_repo = job_package['form_data']['dest_repo']

	# get export context
	export_context = job_package['form_data']['export_context']

	# overwrite
	if 'overwrite' in job_package['form_data']:
		overwrite = True
	else:
		overwrite = False

	# refresh remote
	if 'refresh_remote' in job_package['form_data']:
		refresh_remote = True
	else:
		refresh_remote = False

	# omit checksums
	if 'omit_checksums' in job_package['form_data']:
		omit_checksums = True
	else:
		omit_checksums = False

	# send object with object method
	obj_handle.sendObject(dest_repo, refresh_remote=refresh_remote, overwrite=overwrite, omit_checksums=omit_checksums, export_context=export_context)
	