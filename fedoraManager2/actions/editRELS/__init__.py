# small utility to edit RELS-EXT datastream for objects

# handles
from fedoraManager2.forms import RDF_edit
from fedoraManager2.solrHandles import solr_handle
from fedoraManager2.fedoraHandles import fedora_handle
from fedoraManager2.jobs import getSelPIDs
from fedoraManager2 import models
from fedoraManager2 import db
from flask import Blueprint, render_template, abort, request

#python modules
from lxml import etree
import re

# eulfedora
import eulfedora

# rdflib
from rdflib.compare import to_isomorphic, graph_diff

# fuzzy matching lib
from fuzzywuzzy import fuzz

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


@editRELS.route('/editRELS/regexConfirm', methods=['POST', 'GET'])
def regexConfirm():
		
	# get PIDs	
	PIDs = getSelPIDs()			
	form_data = request.form	

	# search / replace
	orig_string = request.form['raw_xml']
	regex_search = request.form['regex_search'].encode('utf-8')
	regex_replace = request.form['regex_replace'].encode('utf-8')
	new_string = re.sub(regex_search,regex_replace,orig_string)	
		
	#debug
	return_package = {
		"orig_string":orig_string,
		"new_string":new_string,
		"regex_search":regex_search,
		"regex_replace":regex_replace		
	}	

	# check diff - if ratio == 100, XML is identical, simply reordered by RDF query
	if orig_string == new_string:
		return_package['string_match'] = True	
	
	return render_template("editRELS_regexConfirm.html",return_package=return_package)


def editRELS_add_worker(job_package):
	PID = job_package['PID']		
	obj_ohandle = fedora_handle.get_object(PID)	

	form_data = job_package['form_data']	
	
	isMemberOfCollection = form_data['predicate']
	collection_uri = form_data['obj']
	print obj_ohandle.add_relationship(isMemberOfCollection, collection_uri)


def editRELS_edit_worker(job_package):		
	'''
	Takes modified raw RDF XML, applies to all PIDs in job.	
	'''	

	PID = job_package['PID']		
	obj_ohandle = fedora_handle.get_object(PID)

	# get unmodified XML		
	pre_mod_xml = obj_ohandle.rels_ext.content.serialize()

	# get modified XML
	form_data = job_package['form_data']
	raw_xml = form_data['raw_xml']

	# check diff - if ratio == 100, XML is identical, simply reordered by RDF query
	diff_ratio = fuzz.token_set_ratio(raw_xml,pre_mod_xml)	
	print "difference ratio",diff_ratio
	if diff_ratio == 100:
		return "RDF XML un-modified, skipping DB insert and Fedora updating."

	# else, continue
	else:

		# if first PID in job, save pre-modified XML in job_rollback table
		if job_package['step'] == 1:
			db.session.add(models.job_rollback(job_package["job_num"],job_package["username"], "editRELS_edit_worker", pre_mod_xml ))	
			db.session.commit()

		# parse xml, change PID for "about" attribute
		encoded_xml = raw_xml.encode('utf-8')
		parser = etree.XMLParser(ns_clean=True, recover=True, encoding='utf-8')
		XMLroot = etree.fromstring(encoded_xml, parser=parser)
		desc_tag = XMLroot.xpath("//rdf:Description", namespaces=XMLroot.nsmap)
		for desc_tag in XMLroot.xpath("//rdf:Description",namespaces=XMLroot.nsmap):
			desc_tag.attrib['{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about'] = "info:fedora/{PID}".format(PID=PID)
		new_raw = etree.tostring(XMLroot)
		
		# similar to addDS functionality
		# initialized DS object
		newDS = eulfedora.models.DatastreamObject(obj_ohandle, "RELS-EXT", "RELS-EXT", control_group="X")	

		# construct DS object	
		newDS.mimetype = "application/rdf+xml"
		# content		
		newDS.content = new_raw	

		# save constructed object
		print newDS.save()

def editRELS_regex_worker(job_package):		
	
	PID = job_package['PID']		
	obj_ohandle = fedora_handle.get_object(PID)	
	
	# get original RELS-EXT to modify
	orig_string = obj_ohandle.rels_ext.content.serialize()
	
	# get regex parameters
	form_data = job_package['form_data']	

	# search / replace	
	regex_search = form_data['regex_search'].encode('utf-8')
	regex_replace = form_data['regex_replace'].encode('utf-8')
	new_string = re.sub(regex_search,regex_replace,orig_string)		

	# similar to addDS functionality	
	newDS = eulfedora.models.DatastreamObject(obj_ohandle, "RELS-EXT", "RELS-EXT", control_group="X")	

	# construct DS object	
	newDS.mimetype = "application/rdf+xml"
	# content		
	newDS.content = new_string	

	# save constructed object
	print newDS.save()

def editRELS_remove_worker(job_package):
	pass
	
























	