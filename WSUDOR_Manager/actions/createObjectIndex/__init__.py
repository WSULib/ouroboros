# TASK: createObjectIndexes

# python libs
import json

# handles
from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager.solrHandles import solr_handle
from WSUDOR_Manager.forms import solrSearch
from WSUDOR_Manager import utilities
from flask import Blueprint, render_template, abort, request, redirect
import eulfedora

# fedoraManagere2
from WSUDOR_Manager import celery
from celery import Task


# blueprint
createObjectIndex = Blueprint('createObjectIndex', __name__, template_folder='templates', static_folder="static")


'''
Actions where users selects a collection, and an index is applied to each object.
	- based on sorting of PID
	- recorded in "COLLINDEX" datastream as JSON (see wiki for explanation: http://digital.library.wayne.edu/mediawiki/index.php/ObjectCollectionIndex)
'''


@createObjectIndex.route('/createObjectIndex')
@utilities.objects_needed
def index():

	# get form
	form = solrSearch(request.form)

	# dynamically update fields

	# collection selection
	coll_query = {'q':"rels_hasContentModel:*Collection", 'fl':["id","dc_title"], 'rows':1000}
	coll_results = solr_handle.search(**coll_query)
	coll_docs = coll_results.documents
	form.collection_object.choices = [(each['id'].encode('ascii','ignore'), each['dc_title'][0].encode('ascii','ignore')) for each in coll_docs]
	form.collection_object.choices.insert(0,("","All Collections"))	
		
	return render_template("createObjectIndex_index.html",form=form)



@createObjectIndex.route('/createObjectIndex/process', methods=['POST', 'GET'])
def process():
	
	# collect PID
	collection_PID = request.form['collection_object']
	collection_PID_suffix = collection_PID.split(":")[1]	

	# fire celery task
	createObjectIndex_worker.delay(collection_PID_suffix)

	return render_template("createObjectIndex_engaged.html",collection_PID=collection_PID)



@celery.task(name="createObjectIndex_worker")
def createObjectIndex_worker(collection_PID_suffix):
	
	print "Operating on:",collection_PID_suffix

	# build query
	query = {
		"q" : "*%s" % (collection_PID_suffix),
		"rows" : 100,
		"start" : 0,
		"sort" : "id asc"
	}	

	# get collection length
	total_results = solr_handle.search(**query).total_results
	print "Iterating through %s objects..." % (total_results)
	total_iterations = total_results / query['rows']
	if total_results % query['rows'] > 0:
		total_iterations += 1

	print "Total iterations:",total_iterations

	# iterate through objects
	cursor = 0

	# large iterations
	for iteration in range(0,total_iterations):
		# perform new query
		query['start'] = iteration * query['rows']
		print query
		results = solr_handle.search(**query)		

		# for each in smaller query
		for doc in results.documents:
			
			PID = doc['id']
			print "%s gets index: %s" % (PID, cursor)
						
			# retrieve COLLINDEX JSON, edit current collection index, resubmit			
			obj_ohandle = fedora_handle.get_object(PID)
			DS_handle = obj_ohandle.getDatastreamObject("COLLINDEX")
			COLLINDEX_JSON = DS_handle.content			

			# change values	
			collection_key = "wayne:"+collection_PID_suffix
			if DS_handle.exists == True:
				collection_index_dict = json.loads(COLLINDEX_JSON)
				collection_index_dict[collection_key] = {"index":cursor}
			else:
				collection_index_dict = {
					collection_key : {"index":cursor}
				}

			# write new content
			DS_handle = eulfedora.models.DatastreamObject(obj_ohandle, "COLLINDEX", "COLLINDEX", control_group="M")	

			# construct DS object	
			DS_handle.mimetype = "application/json"

			# content		
			DS_handle.content = json.dumps(collection_index_dict)

			# save constructed object
			result = DS_handle.save()
			print "Result for %s: %s" % (PID, result)

			# bump counter
			cursor += 1

	
	return "Finis."















	