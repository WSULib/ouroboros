# small utility to edit RELS-EXT datastream for objects

# handles
from fedoraManager2.forms import RDF_edit
from fedoraManager2.solrHandles import solr_handle
from fedoraManager2.fedoraHandles import fedora_handle
from fedoraManager2.jobs import getSelPIDs
from flask import Blueprint, render_template, abort, request

#python modules
from lxml import etree

# eulfedora
import eulfedora

# rdflib
from rdflib.compare import to_isomorphic, graph_diff



editRELS = Blueprint('editRELS', __name__, template_folder='templates', static_folder="static")


@editRELS.route('/editRELS', methods=['POST', 'GET'])
def index():

	# get PID to examine, if noted
	if request.args.get("PIDnum") != None:
		PIDnum = int(request.args.get("PIDnum"))
	else:
		PIDnum = 0
	
	# get PIDs	
	PIDs = getSelPIDs()	

	# instantiate forms
	form = RDF_edit()		

	# get triples for 1st object
	riquery = fedora_handle.risearch.spo_search(subject="info:fedora/"+PIDs[PIDnum], predicate=None, object=None)
	
	# filter out RELS-EXT and WSUDOR predicates
	riquery_filtered = []
	for s,p,o in riquery:
		if "relations-external" in p or "WSUDOR-Fedora-Relations" in p:
			riquery_filtered.append((p,o))	
	riquery_filtered.sort() #mild sorting applied to group WSUDOR or RELS-EXT	

	# get raw RDF XML for raw_xml field
	obj_ohandle = fedora_handle.get_object(PIDs[PIDnum])	
	raw_xml = obj_ohandle.rels_ext.content.serialize()
	
	return render_template("editRELS_index.html",riquery_filtered=riquery_filtered,PID=PIDs[PIDnum],PIDnum=PIDnum,form=form,raw_xml=raw_xml)



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
	raw_xml = form_data['raw_xml']

	'''
	Potential here to work, but you're going to need to rewrite the 
	PID from the RDF XML.  Classic fedoraManger1 problem...

	Open the XML with lxml, edit that beast.
	'''

	# parse xml, change PID for "about" attribute
	encoded_xml = raw_xml.encode('utf-8')
	parser = etree.XMLParser(ns_clean=True, recover=True, encoding='utf-8')
	XMLroot = etree.fromstring(encoded_xml, parser=parser)
	desc_tag = XMLroot.xpath("//rdf:Description", namespaces=XMLroot.nsmap)
	for desc_tag in XMLroot.xpath("//rdf:Description",namespaces=XMLroot.nsmap):
		desc_tag.attrib['{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about'] = "info:fedora/{PID}".format(PID=PID)
	new_raw = etree.tostring(XMLroot)
	# print new_raw

	# very similar to addDS functionality
	# initialized DS object
	newDS = eulfedora.models.DatastreamObject(obj_ohandle, "RELS-EXT", "RELS-EXT", control_group="X")	

	# construct DS object	
	newDS.mimetype = "application/rdf+xml"
	# content		
	newDS.content = new_raw	

	# save constructed object
	print newDS.save()

def editRELS_remove_worker(job_package):
	pass
	
























	