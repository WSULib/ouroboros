# small utility to edit RELS-EXT datastream for objects

# handles
from fedoraManager2.solrHandles import solr_handle
from fedoraManager2.fedoraHandles import fedora_handle
from flask import Blueprint, render_template, abort


editRELS = Blueprint('editRELS', __name__, template_folder='templates', static_folder="static")


@editRELS.route('/editRELS')
def index():
	'''
	USE FLASK FORMS
	'''
	return render_template("editRELS_index.html")


@editRELS.route('/editRELS/fire')
def fire():
	pass


def editRELS_worker(job_package):
	PID = job_package['PID']		
	obj_ohandle = fedora_handle.get_object(PID)

	form_data = job_package['form_data']	
	
	# PROD
	isMemberOfCollection = 'info:fedora/fedora-system:def/relations-external#{predicate}'.format(predicate=form_data['predicate'])
	collection_uri = 'info:fedora/{object}'.format(object=form_data['object'])
	print obj_ohandle.add_relationship(isMemberOfCollection, collection_uri)
	