# small utility to edit RELS-EXT datastream for objects

# handles
from fedoraManager2.forms import RDF_edit
from fedoraManager2.solrHandles import solr_handle
from fedoraManager2.fedoraHandles import fedora_handle
from fedoraManager2.jobs import getSelPIDs
from flask import Blueprint, render_template, abort

# eulfedora
import eulfedora

# rdflib
from rdflib.compare import to_isomorphic, graph_diff



editRELS = Blueprint('editRELS', __name__, template_folder='templates', static_folder="static")


@editRELS.route('/editRELS')
def index():
	
	# get PIDs	
	PIDs = getSelPIDs()	

	# instantiate forms
	form = RDF_edit()		

	# get triples for 1st object
	riquery = fedora_handle.risearch.spo_search(subject="info:fedora/"+PIDs[0], predicate=None, object=None)
	
	# filter out RELS-EXT and WSUDOR predicates
	riquery_filtered = []
	for s,p,o in riquery:
		if "relations-external" in p or "WSUDOR-Fedora-Relations" in p:
			riquery_filtered.append((p,o))	
	riquery_filtered.sort() #mild sorting applied to group WSUDOR or RELS-EXT	

	# get raw RDF XML for raw_xml field
	obj_ohandle = fedora_handle.get_object(PIDs[0])	
	raw_xml = obj_ohandle.rels_ext.content.serialize()
	
	return render_template("editRELS_index.html",riquery_filtered=riquery_filtered,PID=PIDs[0],form=form,raw_xml=raw_xml)



def editRELS_add_worker(job_package):
	PID = job_package['PID']		
	obj_ohandle = fedora_handle.get_object(PID)	

	form_data = job_package['form_data']	
	
	isMemberOfCollection = form_data['predicate']
	collection_uri = form_data['obj']
	print obj_ohandle.add_relationship(isMemberOfCollection, collection_uri)


def editRELS_edit_worker(job_package):		
	PID = job_package['PID']		
	obj_ohandle = fedora_handle.get_object(PID)

	form_data = job_package['form_data']

	# very similar to addDS functionality
	# initialized DS object
	newDS = eulfedora.models.DatastreamObject(obj_ohandle, "RELS-EXT", "RELS-EXT", control_group="X")	

	# construct DS object	
	newDS.mimetype = "application/rdf+xml"
	# content		
	newDS.content = form_data['raw_xml']	

	# save constructed object
	print newDS.save()

def editRELS_remove_worker(job_package):
	pass
	# PID = job_package['PID']		
	# obj_ohandle = fedora_handle.get_object(PID)

	# form_data = job_package['form_data']


	# # Simple
	# isMemberOfCollection = 'info:fedora/fedora-system:def/relations-external#{predicate}'.format(predicate=form_data['predicate'])
	# collection_uri = 'info:fedora/{object}'.format(object=form_data['object'])
	# print obj_ohandle.add_relationship(isMemberOfCollection, collection_uri)
























	