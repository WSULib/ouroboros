# TASK: createObjectIndexes

# python libs
import json

# handles
from fedoraManager2.fedoraHandles import fedora_handle
from fedoraManager2.solrHandles import solr_handle
from fedoraManager2.forms import solrSearch
from fedoraManager2 import utilities
from flask import Blueprint, render_template, abort, request, redirect
import eulfedora

# fedoraManagere2
from cl.cl import celery
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
		"q" : "*{collection_PID_suffix}".format(collection_PID_suffix=collection_PID_suffix),
		"rows" : 100,
		"start" : 0,
		"sort" : "id asc"
	}	

	# get collection length
	total_results = solr_handle.search(**query).total_results
	print "Iterating through {total_results} objects...".format(total_results=total_results)
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
			print "{PID} gets index: {cursor}".format(PID=PID,cursor=cursor)
						
			# retrieve COLLINDEX JSON, edit current collection index, resubmit			
			obj_ohandle = fedora_handle.get_object(PID)
			DS_handle = obj_ohandle.getDatastreamObject("COLLINDEX")
			COLLINDEX_JSON = DS_handle.content			

			# change values	
			collection_key = "wayne:"+collection_PID_suffix
			if DS_handle.exists == True:
				collection_index_dict = json.loads(COLLINDEX_JSON)
				collection_index_dict[collection_key] = cursor
			else:
				collection_index_dict = {
					collection_key:cursor
				}

			# write new content
			DS_handle = eulfedora.models.DatastreamObject(obj_ohandle, "COLLINDEX", "COLLINDEX", control_group="M")	

			# construct DS object	
			DS_handle.mimetype = "application/json"

			# content		
			DS_handle.content = json.dumps(collection_index_dict)

			# save constructed object
			result = DS_handle.save()
			print "Result for {PID}: {result}".format(PID=PID,result=result)

			# bump counter
			cursor += 1

	
	return "Finis."















	