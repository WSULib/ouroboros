# TASK: addDS - Add Datastream

# handles
from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager.forms import addDSForm
from WSUDOR_Manager import utilities
from flask import Blueprint, render_template, abort
import eulfedora


ACTION_NAME = Blueprint('ACTION_NAME', __name__, template_folder='templates', static_folder="static")


@ACTION_NAME.route('/ACTION_NAME')
@utilities.objects_needed
def index():
	
	# Initial, default index view
	return render_template("ACTION_NAME_index.html",form=form)



def ACTION_NAME_worker(job_package):
	
	# Main working area - this function will fire under celery
	# and output via the established jobs route

	return "TEMPLATE RESPONSE"
	
	