# Python imports
import requests
import ast
import urllib
from paste.util.multidict import MultiDict
import json
import re
import hashlib
import xmltodict
import subprocess
import ldap
import mimetypes

# utilities
from utils import *

# config
from localConfig import *

# modules from WSUDOR_Manager
import WSUDOR_ContentTypes
from WSUDOR_API.fedoraHandles import fedora_handle
from WSUDOR_API.bitStream import BitStream
from WSUDOR_Manager import solrHandles
from WSUDOR_Manager.solrHandles import solr_handle
from WSUDOR_Manager import utilities
from WSUDOR_Manager import models
from WSUDOR_Manager import db


'''
Description: This file represents all functions available to the WSUDOR_API.  

Function Format:
	def [functionName](getParams):
		<triple quotes>
		Description of function, expected inputs, returns, etc.
		</triple quotes>
'''


#######################################################################################################################
# --------------------------------------------------------------------------------------------------------------------#
# SOLR RELATED                                                                                                        #
# --------------------------------------------------------------------------------------------------------------------#
#######################################################################################################################

def solrGetFedDoc(getParams):
#get title and everything from a SOLR request
######################################################################################################################

	'''
	Retrieve Single Document
	'''

	# query dictionary (qd)
	PID=getParams['PID'][0]
	PID = PID.replace(":", "\:")
	qd = {
		'q' : 'id:%s' % (PID),
		'fl' : ['id', 'mods*', 'dc*', 'rels*', 'obj*', 'facet*', 'last_modified']
	}

	# Send Query
	sr = solr_handle.search(**qd)
	return json.dumps(sr.raw_content)

	

def solrSearch(getParams):
######################################################################################################################	
	
	'''
	Primary Search.
	Build dictionary for query to mysolr
	'''

	# query dictionary (qd)
	qd = {}

	# HARD-CODE
	# sorts date result 
	qd['f.dc_date.facet.sort'] = ["index"]
	# no limit on facets
	qd['facet.limit'] = ["-1"]
	# implies "AND" operator for all blank spaces when q.op not explicitly set
	if 'q.op' not in getParams:
		qd['q.op'] = ["AND"]

	# QUERY	
	if 'q' in getParams:
		q_string = getParams['q'][0]
		# if 
		if q_string.startswith('wayne:'):
			q_string = q_string.replace(":","\:")
		qd['q'] = q_string		
	else:		
		qd['q'] = [""]

	# FACETS	
	if 'facets[]' in getParams:
		qd['facet.field'] = [ facet for facet in getParams['facets[]'] ]
		qd['facet.method'] = 'fc'

	# FILTER QUERIES	
	if 'fq[]' in getParams:
		qd['fq'] = [ facet for facet in getParams['fq[]'] ]
	else:
		# create empty list for other fq's
		qd['fq'] = []

	# BACKDOOR FOR VIEWING ALL ITEMS	
	if 'fullview' in getParams and getParams['fullview'][0] == "true":
		pass
	else:		
		qd['fq'].append('rels_isDiscoverable:True')


	# FILTER QUERIES (FL)
	qd['fl'] = [ "id", "mods*", "dc*", "rels*", "obj*", "last_modified" ]


	# OTHER PARAMS
	skip_processing = ["raw","fullview","facets[]","fq[]","q"]	
	for k in getParams:
		if k not in skip_processing:
			qd[k] = getParams[k][0]

	# Send and return query
	sr = solr_handle.search(**qd)
	return json.dumps(sr.raw_content)


def solrCoreGeneric(getParams):
######################################################################################################################	
	
	'''
	EXPERIMENTAL
	Build dictionary for query to mysolr
	'''

	# query dictionary (qd)
	qd = {}

	# HARD-CODE
	# sorts date result 
	qd['f.dc_date.facet.sort'] = ["index"]
	# no limit on facets
	qd['facet.limit'] = ["-1"]
	# implies "AND" operator for all blank spaces when q.op not explicitly set
	if 'q.op' not in getParams:
		qd['q.op'] = ["AND"]

	# QUERY	
	if 'q' in getParams:
		qd['q'] = getParams['q'][0]
	else:		
		qd['q'] = [""]

	# FACETS	
	if 'facets[]' in getParams:
		qd['facet.field'] = [ facet for facet in getParams['facets[]'] ]

	# FILTER QUERIES	
	if 'fq[]' in getParams:
		qd['fq'] = [ facet for facet in getParams['fq[]'] ]
	else:
		# create empty list for other fq's
		qd['fq'] = []

	# OTHER PARAMS
	skip_processing = ["facets[]","fq[]","q"]
	for k in getParams:
		qd[k] = getParams[k][0]

	# Send and return query	
	sr = solrHandles.onDemand(getParams['solrCore'][0]).search(**qd)
	return json.dumps(sr.raw_content)



def getCollectionMeta(getParams):
######################################################################################################################
	'''
	Note: using WSUDOR object methods.
	'''

	# object handle
	PID=getParams['PID'][0]
	obj_handle = WSUDOR_ContentTypes.WSUDOR_Object(PID)

	# get collection pids
	try:
		collection_pids = obj_handle.SolrDoc.asDictionary()['rels_isMemberOfCollection']

		# get collection solr docs
		search_string = "id:("+" OR ".join([ collection_pid.split("/")[1].replace(":","\:") for collection_pid in obj_handle.SolrDoc.asDictionary()['rels_isMemberOfCollection']])+")"
		solr_results = solr_handle.search(**{"q":search_string})

		return json.dumps(solr_results.documents)

	except:
		return json.dumps({"result":"no parent collection objects found"})


def getUserFavorites(getParams):
######################################################################################################################

	# establish baseURL
	baseURL = "http://localhost/solr4/users/select?"

	# set solrParams
	solrParams = ast.literal_eval(getParams['solrParams'][0])	
	print "Solr Search Params:", solrParams

	# hard-code some server side parameters
	solrParams['f.dc_date.facet.sort'] = "index"
	solrParams['facet.limit'] = "-1"	

	# facets
	if 'facets[]' in solrParams:
		for facet in solrParams['facets[]']:
			baseURL += ("facet.field="+facet+"&")	

	# filter queries
	if "fq[]" in solrParams:
		for fq in solrParams['fq[]']:
			baseURL += ("fq="+fq+"&")	

	processed = ["raw","fullview","facets[]","fq[]"]

	# add all other parameters	
	for k in solrParams:
		if k not in processed:
			baseURL += (k+"="+str(solrParams[k])+"&")	

	## DEBUG
	print "\n\n***SOLR PARAMS***",solrParams
	print "\n\n***BASE URL***",baseURL,"\n\n"

	# make Solr Request
	r = requests.get(baseURL)			
	jsonString = r.text	
	return jsonString


def solrTranslationHash(args):
# function to return PIDs and their Labels in JS Hash that can / is used to cleanup front-end interfaces, 
# and interact with things in meaningful ways
# Note: Makes sense to key off PID for logic, as these are less likely to change than the Object Label / DC Title field
######################################################################################################################	


	# list of queries to translate results
	queriesToTrans = [
		# all Collection objects
		"http://localhost/solr4/%s/select?q=rels_hasContentModel%%3Ainfo%%5C%%3Afedora%%2FCM%%5C%%3ACollection&fl=id+dc_title&wt=json&indent=true&rows=100" % (SOLR_SEARCH_CORE),
		# all Content Models Types
		"http://localhost/solr4/%s/select?q=id%%3ACM*&rows=100&fl=id+dc_title&wt=json&indent=true&rows=100" % (SOLR_SEARCH_CORE)
	]

	# run query and add to hash
	transDict = {}
	for query in queriesToTrans:
		r = requests.get(query)
		tempDict = ast.literal_eval(r.text)['response']['docs']
		for each in tempDict:
			try:
				transDict[("info:fedora/"+each['id'])] = each['dc_title'][0]
			except:
				print "solrTranslationHash could not unite PID and dc_title"

	# churn to JSON and return
	transJSONpackage = json.dumps(transDict)
	return transJSONpackage


# # experiemtnal function to query and update /pubstore core in Solr4.
# # this core is used as a quasi-datastore at this point, perhaps exclusively for ephemeral data
# def pubStore(getParams):
# 	urlsuff = getParams['urlsuff'][0]
# 	solrString = getParams['json'][0]	

# 	# print solrString

# 	baseURL = "http://localhost/solr4/pubstore/%s" % (urlsuff)
# 	# baseURL = "http://localhost/solr4/pubstore/update/json?commit=true"
# 	# print "Going to this URL:",baseURL

# 	# json post
# 	if "update" in urlsuff:
# 		headersDict = {
# 			"Content-type":"application/json"
# 		}

# 		r = requests.post(baseURL, data=solrString, headers=headersDict)

# 	# get
# 	if "select" in urlsuff:
# 		solrParams = ast.literal_eval(solrString)
# 		r = requests.get(baseURL, params=solrParams)

# 	jsonString = r.text
# 	return jsonString




#######################################################################################################################
# --------------------------------------------------------------------------------------------------------------------#
# FEDORA RELATED                                                                                                      #
# --------------------------------------------------------------------------------------------------------------------#
#######################################################################################################################

# get object state
def getObjectXML(getParams):	
	o = fedora_handle.get_object(getParams['PID'][0])

	#check if valid PID
	if o.exists == False:
		outputDict = {"object_status" : 'Absent' }
	else:
		outputDict = {"object_status" : o.state }

	output = json.dumps(outputDict)
	return output

# gets children for single PID
def isMemberOf(getParams):

	baseURL = "http://localhost/fedora/risearch"
	risearch_query = "select $subject from <#ri> where <info:fedora/%s> <info:fedora/fedora-system:def/relations-external#isMemberOf> $subject" (getParams['PID'][0])
	risearch_params = {
	'type': 'tuples',
	'lang': 'itql',
	'format': 'json',
	'limit':'',
	'dt': 'on',
	'query': risearch_query
	}

	# r = requests.post(baseURL, auth=(WSUDOR_API_USER, WSUDOR_API_PASSWORD), data=risearch_params)
	r = fedora_handle.api.session.get(baseURL, params=risearch_params)
	# strip risearch namespace "info:fedora"
	jsonString = r.text.replace('info:fedora/','')			
	return jsonString

# get isMemberOf children for single PID
def hasMemberOf(getParams):
	baseURL = "http://localhost/fedora/risearch"
	risearch_query = "select $memberTitle $object from <#ri> where $object <info:fedora/fedora-system:def/relations-external#isMemberOf> <info:fedora/%s> and $object <http://purl.org/dc/elements/1.1/title> $memberTitle order by $memberTitle" % (getParams['PID'][0])
	risearch_params = {
	'type': 'tuples',
	'lang': 'itql',
	'format': 'json',
	'limit':'',
	'dt': 'on',
	'query': risearch_query
	}

	# r = requests.post(baseURL, auth=(WSUDOR_API_USER, WSUDOR_API_PASSWORD), data=risearch_params)
	r = fedora_handle.api.session.get(baseURL, params=risearch_params)
	# strip risearch namespace "info:fedora"
	jsonString = r.text.replace('info:fedora/','')			
	return jsonString

# get parents for PID
def isMemberOfCollection(getParams):

	baseURL = "http://localhost/fedora/risearch"	
	risearch_query = "select $collectionTitle $subject from <#ri> where <info:fedora/%s> <info:fedora/fedora-system:def/relations-external#isMemberOfCollection> $subject and $subject <http://purl.org/dc/elements/1.1/title> $collectionTitle" % (getParams['PID'][0])

	risearch_params = {
	'type': 'tuples',
	'lang': 'itql',
	'format': 'json',
	'limit':'',
	'dt': 'on',
	'query': risearch_query
	}

	# r = requests.post(baseURL, auth=(WSUDOR_API_USER, WSUDOR_API_PASSWORD), data=risearch_params)
	r = fedora_handle.api.session.get(baseURL, params=risearch_params)
	# strip risearch namespace "info:fedora"
	jsonString = r.text.replace('info:fedora/','')
	return jsonString


# get isMemberOfCollection children for single PID (also return isRepresentedBy attribute)
def hasMemberOfCollection(getParams):	
	baseURL = "http://localhost/fedora/risearch"
	risearch_query = "select $memberTitle $object $isRepBy from <#ri> where $object <info:fedora/fedora-system:def/relations-external#isMemberOfCollection> <info:fedora/%s> and $object <http://purl.org/dc/elements/1.1/title> $memberTitle and $object <info:fedora/fedora-system:def/relations-external#isMemberOfCollection> <info:fedora/%s> and $object <wsudor:isRepresentedBy> $isRepBy order by $memberTitle" % (getParams['PID'][0],getParams['PID'][0])
	risearch_params = {
	'type': 'tuples',
	'lang': 'itql',
	'format': 'json',
	'limit':'',
	'dt': 'on',
	'query': risearch_query
	}

	# r = requests.post(baseURL, auth=(WSUDOR_API_USER, WSUDOR_API_PASSWORD), data=risearch_params)
	r = fedora_handle.api.session.get(baseURL, params=risearch_params)
	# strip risearch namespace "info:fedora"
	jsonString = r.text.replace('info:fedora/','')			
	return jsonString


#returns all siblings, from all parent Collections
def getSiblings(getParams):
	baseURL = "http://localhost/fedora/risearch"
	risearch_query = "select $collection $sibling from <#ri> where <info:fedora/%s> <info:fedora/fedora-system:def/relations-external#isMemberOfCollection> $collection and $sibling <info:fedora/fedora-system:def/relations-external#isMemberOfCollection> $collection" % (getParams['PID'][0])
	risearch_params = {
	'type': 'tuples',
	'lang': 'itql',
	'format': 'csv',
	'limit':'',
	'dt': 'on',
	'query': risearch_query
	}

	# prepare as JSON dict
	# r = requests.post(baseURL, auth=(WSUDOR_API_USER, WSUDOR_API_PASSWORD), data=risearch_params)
	r = fedora_handle.api.session.get(baseURL, params=risearch_params)
	# strip risearch namespace "info:fedora"
	jsonString = r.text.replace('info:fedora/','')
	lines = jsonString.split("\n")	
	del lines[0]
	del lines[-1]

	collections = {}
	for line in lines:
		comps = line.split(",")
		if comps[0] not in collections:
			collections[comps[0]] = []
			collections[comps[0]].append(comps[1])
		else:
			collections[comps[0]].append(comps[1])		

	results = []
	for each in collections:
		results.append((each,collections[each]))
	
	JSONoutput = json.dumps(results)
	return JSONoutput


# return Fedora MODS datastream
def fedoraMODS(getParams):
	baseURL = "http://localhost/fedora/objects/%s/datastreams/MODS/content" % (getParams['PID'][0])
	r = requests.get(baseURL, auth=(WSUDOR_API_USER, WSUDOR_API_PASSWORD))			
	xmlString = r.text
	#convert XML to JSON with "xmltodict"
	outputDict = xmltodict.parse(xmlString)
	output = json.dumps(outputDict)
	return output


# return walk of serial volumes / issues in tidy package
def serialWalk(getParams):
	baseURL = "http://localhost/fedora/risearch"
	risearch_query = "SELECT ?volume ?volumeTitle ?issue $issueTitle WHERE {{ ?volume  <fedora-rels-ext:isMemberOfCollection> <info:fedora/%s> .  $volume <http://purl.org/dc/elements/1.1/title> ?volumeTitle . ?volume  <fedora-rels-ext:hasContentModel> <info:fedora/CM:Volume> . ?issue <fedora-rels-ext:isMemberOf>  ?volume . ?issue <fedora-rels-ext:hasContentModel> <info:fedora/CM:Issue> . $issue <http://purl.org/dc/elements/1.1/title> $issueTitle .  }} ORDER BY ASC(?issue)" % (getParams['PID'][0])
	risearch_params = {
		'type': 'tuples',
		'lang': 'sparql',
		'format': 'json',
		'limit':'',
		'dt': 'on',
		'query': risearch_query
	}

	# r = requests.post(baseURL, auth=(WSUDOR_API_USER, WSUDOR_API_PASSWORD), data=risearch_params)
	r = fedora_handle.api.session.get(baseURL, params=risearch_params)
	# strip risearch namespace "info:fedora"
	jsonString = r.text.replace('info:fedora/','')			
	return jsonString


# # return symlink (created or retrieved) to object in datastreamStore
# def fedDataSpy(getParams):

# 	outputDict = {}

# 	PID = getParams['PID'][0]
# 	DS = getParams['DS'][0]	
	
# 	outputDict = makeSymLink(PID, DS)

# 	jsonString = json.dumps(outputDict)
# 	return jsonString


# get isPartOf children for single PID
def hasPartOf(getParams):	
	baseURL = "http://localhost/fedora/risearch"
	risearch_query = "select $object from <#ri> where $object <info:fedora/fedora-system:def/relations-internal#isPartOf> <info:fedora/%s>" % (getParams['PID'][0])
	risearch_params = {
	'type': 'tuples',
	'lang': 'itql',
	'format': 'json',
	'limit':'',
	'dt': 'on',
	'query': risearch_query
	}

	# r = requests.post(baseURL, auth=(WSUDOR_API_USER, WSUDOR_API_PASSWORD), data=risearch_params)
	r = fedora_handle.api.session.get(baseURL, params=risearch_params)
	# strip risearch namespace "info:fedora"	
	handle = json.loads(r.text)

	for each in handle['results']:
		each['pid'] = each['object'].split("/")[1]
		each['ds_id'] = each['object'].split("/")[2]

	jsonString = json.dumps(handle)

	return jsonString


# get total size of object
def getObjectSize(getParams):
	
	PID = getParams['PID'][0]
	obj_handle = WSUDOR_ContentTypes.WSUDOR_Object(PID)

	try:
		# normalized WSUDOR ContentType
		if obj_handle != False:
			return json.dumps( obj_handle.objSizeDict )

		# else, try use Eulfedora API raw	
		else:

			ohandle = fedora_handle.get_object(PID)

			size_dict = {}
			tot_size = 0

			# loop through datastreams, append size to return dictionary
			for ds in ohandle.ds_list:
				ds_handle = ohandle.getDatastreamObject(ds)
				ds_size = ds_handle.size
				tot_size += ds_size
				size_dict[ds] = ( ds_size, utilities.sizeof_fmt(ds_size) )

			size_dict['total_size'] = (tot_size, utilities.sizeof_fmt(tot_size) )
			print size_dict
			return json.dumps( size_dict )

	except Exception,e:
		return json.dumps({"message":"Could not determine size of object. Error: %s" % (str(e)) })		



# generate hierarchical family tree
def hierarchicalTree(getParams):

	# parent
	baseURL = "http://localhost/fedora/risearch"
	risearch_query = '''
	select $parent $parentTitle from <#ri> where
	    <info:fedora/%s> 
	    <wsudor:hasParent> 
	    $parent
	and 
	    $parent
	    <dc:title>
	    $parentTitle	
    order by $parentTitle

	''' % (getParams['PID'][0])
	risearch_params = {
	'type': 'tuples',
	'lang': 'itql',
	'format': 'json',
	'limit':'',
	'dt': 'on',
	'query': risearch_query
	}
	r = fedora_handle.api.session.get(baseURL, params=risearch_params)
	# strip risearch namespace "info:fedora"
	parent_jsonString = r.text.replace('info:fedora/','')
	parent_dict = json.loads(parent_jsonString)

	# parent siblings
	baseURL = "http://localhost/fedora/risearch"
	risearch_query = '''
	select $parentSibling $parentSiblingTitle from <#ri> where 
	    <info:fedora/%s> 
	    <wsudor:hasParent> 
	    $parent
	and 
	    $parent
	    <dc:title>
	    $parentTitle
	and
	    $parent
	    <wsudor:hasParent>
	    $grandParent
	and
	    $parentSibling
	    <wsudor:hasParent>
	    $grandParent
	and 
	    $parentSibling
	    <dc:title>
	    $parentSiblingTitle
    order by $parentSiblingTitle

	''' % (getParams['PID'][0])
	risearch_params = {
	'type': 'tuples',
	'lang': 'itql',
	'format': 'json',
	'limit':'',
	'dt': 'on',
	'query': risearch_query
	}

	r = fedora_handle.api.session.get(baseURL, params=risearch_params)
	# strip risearch namespace "info:fedora"
	parent_sibling_jsonString = r.text.replace('info:fedora/','')
	parent_sibling_dict = json.loads(parent_sibling_jsonString)

	# siblings
	baseURL = "http://localhost/fedora/risearch"
	risearch_query = '''
	select $sibling $siblingTitle from <#ri> where 
	    <info:fedora/%s> 
	    <wsudor:hasParent> 
	    $parent
	and 
	    $sibling
	    <wsudor:hasParent>
	    $parent
	and 
	    $sibling
	    <dc:title>
	    $siblingTitle
    order by $siblingTitle

	''' % (getParams['PID'][0])
	risearch_params = {
	'type': 'tuples',
	'lang': 'itql',
	'format': 'json',
	'limit':'',
	'dt': 'on',
	'query': risearch_query
	}

	r = fedora_handle.api.session.get(baseURL, params=risearch_params)
	# strip risearch namespace "info:fedora"
	sibling_jsonString = r.text.replace('info:fedora/','')
	sibling_dict = json.loads(sibling_jsonString)

	# reomve current PID from siblings
	for idx, val in enumerate(sibling_dict['results']):
		if val['sibling'] == getParams['PID'][0]:
			del sibling_dict['results'][idx]

	# children
	baseURL = "http://localhost/fedora/risearch"
	risearch_query = '''
	select $child $childTitle from <#ri> where 
	    $child
	    <wsudor:hasParent> 
	    <info:fedora/%s> 
	and
	    $child
	    <dc:title>
	    $childTitle
    order by $childTitle

	''' % (getParams['PID'][0])
	risearch_params = {
	'type': 'tuples',
	'lang': 'itql',
	'format': 'json',
	'limit':'',
	'dt': 'on',
	'query': risearch_query
	}

	r = fedora_handle.api.session.get(baseURL, params=risearch_params)
	# strip risearch namespace "info:fedora"
	child_jsonString = r.text.replace('info:fedora/','')
	child_dict = json.loads(child_jsonString)


	treeDict = {
		"parent":parent_dict,
		"parent_siblings":parent_sibling_dict,
		"siblings":sibling_dict,
		"children":child_dict
	}


	return json.dumps(treeDict)



#######################################################################################################################
# --------------------------------------------------------------------------------------------------------------------#
# DIAGNOSTICS / TESTING                                                                                               #
# --------------------------------------------------------------------------------------------------------------------#
#######################################################################################################################


'''
Notes:
----------------------
Considering not using Ghost.py at this point, for stability and performance reasons.	

Currently, testing metadata and search calls through the API.  
	- This *could* run through dozens of objects, very quickly
	- All page rendering functions commented out
	- Difficult for a variety of reasons
		- Ghost.py has to run as main thread, so seperate script (could hold up Ouro)
		- -X server
		- can bring down Ouro pretty easily

Looking into a "robo-user" that will walk collections always.
'''

# GET ITEMS
################################################################################################

# This function produces an representative list of PIDs to check 
def getItems():
	# return an array of PIDs from current collections
	pass


# ALL TEST
################################################################################################
# function for testing overall integrity of front-end system
# runs tests from below, integrating results into one JSON package, with True / False verdict

def integrityTest(getParams):

	# create dictionary that will equate function / task with True / False and result message		
	resultsList = []	

	# run functions here
	############################################################################################
	# Single Objects
	resultsList.append({"getSingleObjectSolrMetadata":json.loads(getSingleObjectSolrMetadata({"PID":"wayne:CFAIEB01a002"}))})
	# resultsList.append({"singleObjectPageRender":json.loads(singleObjectPageRender({"PID":"wayne:CFAIEB01a002"}))})
	
	# Search / Browse / Collections
	resultsList.append({"solrSearchKnownTerm":json.loads(solrSearchKnownTerm({"search_term":"Michigan"}))})
	resultsList.append({"solrSearchCollectionObjects":json.loads(solrSearchCollectionObjects({"search_term":"rels_hasContentModel%3Ainfo%5C%3Afedora%2FCM%5C%3ACollection"}))})
	# resultsList.append({"searchPageRender":json.loads(searchPageRender({"search_term":"Michigan"}))})
	# resultsList.append({"collectionPageRender":json.loads(collectionPageRender({False}))})
	############################################################################################

	# read all functions, determine if any false present, breaks if so
	# simpler: one False will sully the True
	final_verdict = True
	for eachFunction in resultsList:	# json.loads		
		for funcName in eachFunction:
			result_dict = eachFunction[funcName]						
			# eachFunction = json.loads(eachFunction)	
			if result_dict['result'] == True:				
				continue
			elif result_dict['result'] == False:
				final_verdict = False
				break

	# return resultsDict as function response
	return json.dumps({
			'integrityTest_result': final_verdict,
			'function_log':resultsList # need to recursively decode the JSON here
		})

	

# INDIVIDUAL TEST FUNCTIONS
################################################################################################
# each function should contain a human-readable SUCCESS / FAILURE expectation and description
	# as triple-quoted string, which bubbles up to help / description pages.
# each function response should build and return json.loads(returnDict)


# Single Objects
################################################################################################
def getSingleObjectSolrMetadata(getParams):
	'''
	returns the metadata for a single object, from Solr, via the WSUDOR_API
	SUCCESS: solr.response.docs > 0
	FAILURE: solr.response.docs == 0
	'''
	# solr search	
	result = solrGetFedDoc({"PID":[getParams['PID']]})	
	try:
		result_handle = json.loads(result) # tests JSON validity	
		numFound = result_handle['response']['numFound']
		if numFound == 1:
			returnDict = {
				"result":True,
				'msg':"Solr Metadata returned correctly, numFound = 1"
			}
		else:
			returnDict = {
				"result":False,
				'msg':"Response successful, but numFound wrong.  Should be 1, found %s" % (str(numFound))
			}
		# return result # return JSON for API response
	except Exception, e:
		returnDict = {
			'result' : False,
			'msg' : json.dumps(e)
		}		

	return json.dumps(returnDict)


def singleObjectPageRender(getParams):	
	'''
	Renders a singleObject page with Ghost.py, checks status code.
	SUCCESS: status code == 200
	FAILURE: status code == 404 or 503
	'''
	# solr search	
	PID = getParams['PID']
	URL = "http://%s/digitalcollections/item?id=%s" % (localConfig.APP_HOST, PID)

	try:				
		http_status_string = subprocess.check_output("python WSUDOR_API/functions/ghostGetHttpStatus.py %s" % (URL), shell=True)
		http_status = int(http_status_string)

		print "http status:", http_status

		if http_status == 200:
			returnDict = {
				"result":True,
				'msg':"Ghost.py rendering successful, HTTP status 200."
			}		
		else:
			returnDict = {
				"result":False,
				'msg':"Ghost.py rendering unsuccessful, HTTP status %s." % (str(http_status))
			}		
	
	except Exception, e:
		returnDict = {
			'result' : False,
			'msg' : json.dumps(e)
		}		

	print "Page Rendering:",returnDict

	return json.dumps(returnDict)



# Search / Browse / Collections
################################################################################################
def solrSearchCollectionObjects(getParams):
	'''
	returns results for all collection objects, from Solr, via the WSUDOR_API
	SUCCESS: solr.response.docs > 0
	FAILURE: solr.response.docs == 0
	'''
	# solr search	

	result = solrSearch({"q":[getParams['search_term']],"wt":["json"]})
	
	try:
		result_handle = json.loads(result) # tests JSON validity	
		numFound = result_handle['response']['numFound']
		if numFound > 0:
			returnDict = {
				"result":True,
				'msg':"Solr Search successful, numFound > 0"
			}
		else:
			returnDict = {
				"result":False,
				'msg':"Response successful, but numFound wrong.  Should be > 0, found %s" % (str(numFound))
			}
		# return result # return JSON for API response
	except Exception, e:
		returnDict = {
			'result' : False,
			'msg' : json.dumps(e)
		}		

	return json.dumps(returnDict)


def solrSearchKnownTerm(getParams):
	'''
	returns results for word "Michigan", from Solr, via the WSUDOR_API
	SUCCESS: solr.response.docs > 0
	FAILURE: solr.response.docs == 0
	'''
	# solr search	

	result = solrSearch({"q":[getParams['search_term']],"wt":["json"]})
	
	try:
		result_handle = json.loads(result) # tests JSON validity	
		numFound = result_handle['response']['numFound']
		if numFound > 0:
			returnDict = {
				"result":True,
				'msg':"Solr Search successful, numFound > 0"
			}
		else:
			returnDict = {
				"result":False,
				'msg':"Response successful, but numFound wrong.  Should be > 0, found %s" % (str(numFound))
			}
		# return result # return JSON for API response
	except Exception, e:
		returnDict = {
			'result' : False,
			'msg' : json.dumps(e)
		}		

	return json.dumps(returnDict)


def searchPageRender(getParams):	
	'''
	Renders a singleObject page with Ghost.py, checks status code.
	SUCCESS: status code == 200
	FAILURE: status code == 404 or 503
	'''
	# solr search
	URL = "http://%s/digitalcollections/search.php?q=%s" % (localConfig.APP_HOST, getParams['search_term'])

	try:				
		http_status_string = subprocess.check_output("python WSUDOR_API/functions/ghostGetHttpStatus.py %s" % (URL), shell=True)
		http_status = int(http_status_string)

		print "http status:", http_status

		if http_status == 200:
			returnDict = {
				"result":True,
				'msg':"Ghost.py rendering successful, HTTP status 200."
			}		
		else:
			returnDict = {
				"result":False,
				'msg':"Ghost.py rendering unsuccessful, HTTP status %s." % (str(http_status))
			}		
	
	except Exception, e:
		returnDict = {
			'result' : False,
			'msg' : json.dumps(e)
		}		

	print "Page Rendering:",returnDict

	return json.dumps(returnDict)


def collectionPageRender(getParams):	
	'''
	Renders a singleObject page with Ghost.py, checks status code.
	SUCCESS: status code == 200
	FAILURE: status code == 404 or 503
	'''
	# solr search
	URL = "http://%s/digitalcollections/allcollections.php" % (localConfig.APP_HOST)

	try:				
		http_status_string = subprocess.check_output("python WSUDOR_API/functions/ghostGetHttpStatus.py %s" % (URL), shell=True)
		http_status = int(http_status_string)

		print "http status:", http_status

		if http_status == 200:
			returnDict = {
				"result":True,
				'msg':"Ghost.py rendering successful, HTTP status 200."
			}		
		else:
			returnDict = {
				"result":False,
				'msg':"Ghost.py rendering unsuccessful, HTTP status %s." % (str(http_status))
			}		
	
	except Exception, e:
		returnDict = {
			'result' : False,
			'msg' : json.dumps(e)
		}		

	print "Page Rendering:",returnDict

	return json.dumps(returnDict)




#######################################################################################################################
# --------------------------------------------------------------------------------------------------------------------#
# LDAP / USER AUTHENTICATION                                                                                          #
# --------------------------------------------------------------------------------------------------------------------#
#######################################################################################################################

'''
Convert all user accounts to MySQL model.
	userSearch()
	WSUDORuserAuth()
	cookieAuth()
	createUserAccount()
	authUser()
	getUserInfo()
'''

def userSearch(getParams):
######################################################################################################################

	# establish baseURL
	baseURL = "http://localhost/solr4/users/select?"

	solrParams = {}
	solrParams['q'] = 'id:'+getParams['username'][0]
	solrParams["wt"] = "python"	

	# add all other parameters	
	for k in solrParams:		
		baseURL += (k+"="+str(solrParams[k])+"&")	

	## DEBUG
	# print "\n\n***SOLR PARAMS***",solrParams
	# print "\n\n***BASE URL***",baseURL,"\n\n"

	# make Solr Request, save to userDict
	r = requests.get(baseURL)				
	userDict = ast.literal_eval(r.text)
	# print userDict

	# prepare dict to convert to JSON and return
	userReturnDict = {}

	# check if username extant
	if userDict['response']['numFound'] != 0:
		# set some parameters of return dictionary
		userReturnDict['extant'] = True
		userReturnDict['displayName'] = userDict['response']['docs'][0]['user_displayName'][0]
		userReturnDict['username'] = userDict['response']['docs'][0]['user_username'][0]
		userReturnDict['user_WSU'] = userDict['response']['docs'][0]['user_WSU'][0]
		# userReturnDict['clientHash'] = userDict['response']['docs'][0]['user_hash'][0]		

	# username not found
	else:
		print "User account not found..."
		userReturnDict['extant'] = False

	# print userReturnDict
	jsonString = json.dumps(userReturnDict)

	return jsonString



def WSUDORuserAuth(getParams):
######################################################################################################################

	# expectimg username, clientHash
	# get hash for username from solr (don't need password), compare

	# establish baseURL
	baseURL = "http://localhost/solr4/users/select?"

	solrParams = {}
	solrParams['q'] = 'id:'+getParams['username'][0]
	solrParams["wt"] = "python"	

	# add all other parameters	
	for k in solrParams:		
		baseURL += (k+"="+str(solrParams[k])+"&")	

	# make Solr Request, save to userDict
	r = requests.get(baseURL)				
	userDict = ast.literal_eval(r.text)
	# print "Results of WSUDOR password check:"
	# print userDict

	# prepare dict to convert to JSON and return
	userReturnDict = {}

	# check hash match
	# gen hash	
	hashString = getParams['username'][0]+getParams['password'][0]+USER_ACCOUNT_SALT
	clientHash = hashlib.sha256(hashString).hexdigest()

	if clientHash == userDict['response']['docs'][0]['user_hash'][0]:
		print "WSUDOR credentials verified."
		userReturnDict['WSUDORcheck'] = True
		userReturnDict['clientHash'] = userDict['response']['docs'][0]['user_hash'][0]
	else:
		print "WSUDOR credentials do NOT match."
		userReturnDict['WSUDORcheck'] = False

	# print userReturnDict
	jsonString = json.dumps(userReturnDict)

	return jsonString


def cookieAuth(getParams):
######################################################################################################################

	# expectimg username and hash
	# get hash for username from solr (don't need password), compare

	# establish baseURL
	baseURL = "http://localhost/solr4/users/select?"
	print "running cookieAuth"
	# print getParams

	# check for clientHash
	if 'clientHash' not in getParams:
		print "clientHas not provided, aborting"
		userReturnDict['hashMatch'] = False	
		# print userReturnDict
		jsonString = json.dumps(userReturnDict)	
		return jsonString

	solrParams = {}
	solrParams['q'] = 'id:'+getParams['username'][0]
	solrParams["wt"] = "python"	

	# add all other parameters	
	for k in solrParams:		
		baseURL += (k+"="+str(solrParams[k])+"&")	

	## DEBUG
	# print "\n\n***SOLR PARAMS***",solrParams
	# print "\n\n***BASE URL***",baseURL,"\n\n"

	# make Solr Request, save to userDict
	r = requests.get(baseURL)				
	userDict = ast.literal_eval(r.text)
	# print "Results of WSUDOR password check:"
	# print userDict

	# prepare dict to convert to JSON and return
	userReturnDict = {}

	# check hash match
	if getParams['clientHash'][0] == userDict['response']['docs'][0]['user_hash'][0]:
		print "account hashes match"
		userReturnDict['hashMatch'] = True
	else:
		print "account hasshes do NOT match."
		userReturnDict['hashMatch'] = False	

	# print userReturnDict
	jsonString = json.dumps(userReturnDict)

	return jsonString


def createUserAccount(getParams):
# function to take jsonAddString, index in Solr, and return confirmation code
######################################################################################################################	

	# print getParams

	# create solrString to add doc
	solrDict = {}
	solrDict['id'] = getParams['id'][0]
	solrDict['user_username'] = getParams['user_username'][0]
	solrDict['user_displayName'] = getParams['user_displayName'][0]
	# not currently storing passwords in solr...authenticating based on matching hash values for now
	# solrDict['user_password'] = getParams['user_password'][0]
	solrDict['user_WSU'] = getParams['user_WSU'][0]
	# create hash of username and password	
	hashString = solrDict['user_username']+getParams['user_password'][0]+USER_ACCOUNT_SALT
	solrDict['user_hash'] = hashlib.sha256(hashString).hexdigest()
	# print solrDict

	solrString = json.dumps(solrDict)
	solrString = "["+solrString+"]"
	# print solrString

	baseURL = "http://localhost/solr4/users/update/json?commit=true"
	headersDict = {
		"Content-type":"application/json"
	}

	r = requests.post(baseURL, data=solrString, headers=headersDict)	
	responseString = json.loads(r.text)

	userReturnDict = {}
	userReturnDict['clientHash'] = solrDict['user_hash']
	userReturnDict['createResponse'] = responseString

	jsonString = json.dumps(userReturnDict)

	return jsonString


def addFavorite(getParams):
# function to take jsonAddString, index in Solr, and return confirmation code
######################################################################################################################	
	solrString = getParams['raw'][0]
	# print solrString	

	baseURL = "http://localhost/solr4/users/update/json?commit=true"
	headersDict = {
		"Content-type":"application/json"
	}

	r = requests.post(baseURL, data=solrString, headers=headersDict)
	jsonString = r.text
	return jsonString


'''
Need to convert sunburnt to mysolr here
'''
# def removeFavorite(getParams):
# # function to take jsonAddString, remove from Solr, and return confirmation code
# ######################################################################################################################	
# 	returnDict = {}

# 	# authenticate user	
# 	username = getParams['username'][0]
# 	providedHash = getParams['userhash'][0]

# 	si = sunburnt.SolrInterface("http://localhost:8080/solr4/users/")	
# 	response = si.query(user_username=username).execute()
# 	recordedHash = response[0]['user_hash'][0]
# 	# print "Provided:",providedHash
# 	# print "Recorded:",recordedHash
# 	if providedHash == recordedHash:
# 		# print "Credentials look good, proceeding."
# 		# delete doc
# 		PID = getParams['PID'][0]
# 		si.delete(username+"_"+PID)
# 		si.commit()

# 		# return response
# 		returnDict['username'] = username
# 		returnDict['favorite_removed'] = PID
# 		return json.dumps(returnDict)

# 	else:
# 		# print "Credentials don't match."
# 		returnDict['status'] = "Credentials don't match."
# 		return json.dumps(returnDict)


def authUser(getParams):
	# try:

	username=getParams['username'][0]
	password=getParams['password'][0]

	returnDict = {}

	###############################################################
	# get clientHash# 
	try:
		userDict = {}
		baseURL = "http://localhost/solr4/users/select?"
		
		solrParams = {}
		solrParams['q'] = 'id:'+username
		solrParams["wt"] = "python"
		# add all other parameters	
		for k in solrParams:		
			baseURL += (k+"="+str(solrParams[k])+"&")	

		# make Solr Request, save to userDict
		r = requests.get(baseURL)				
		userDict = ast.literal_eval(r.text)
		# print "Userdict:",userDict
		# print "\n\n\n"
		# print "FROM SOLR: Results of clientHash retrieval from LDAP authorization:"
		# print userDict['response']['docs'][0]['user_hash'][0]			
		# print "\n\n\n"
		retrieved_clientHash = userDict['response']['docs'][0]['user_hash'][0]
		returnDict['clientHash'] = retrieved_clientHash
	except:
		print "Could not retrieve user hash"
	###############################################################

	# set ldap location, protocol version, and referrals
	l = ldap.initialize("ldaps://directory.wayne.edu:636")
	l.protocol_version = ldap.VERSION3
	l.set_option(ldap.OPT_REFERRALS, 0)

	submitted_username = username
	username = "uid="+submitted_username+",ou=People,DC=wayne,DC=edu"
	password = password
	if password == "":
		jsonString = '{"desc":"no password"}'			
		return jsonString
	else:	
		try:
			l.bind_s(username, password)	
		except ldap.LDAPError, e:
			jsonString = json.dumps(e.message)
			return jsonString

	# set baseDN, scope (SUBTREE searches searches for user and children), attributes
	baseDN = "dc=wayne,dc=edu"
	searchScope = ldap.SCOPE_SUBTREE
	retrieveAttributes = ['firstDotLast','givenName','uid']
	searchFilter = "uid="+submitted_username

	# if works, correct credentials and successful
	try:
		ldap_result_id = l.search(baseDN, searchScope, searchFilter, retrieveAttributes)
		result_set = list()
		result_type, result_data = l.result(ldap_result_id)
		for data in result_data:
			if data[0]:
				result_set.append(data)
		# jsonString = json.dumps(result_set)
		################################################
		# Couching in dictionary
		returnDict['LDAP_result_set'] = result_set			
		jsonString = json.dumps(returnDict)
		################################################
		return jsonString
	except ldap.LDAPError, e:
		jsonString = json.dumps(e.message)
		return jsonString


def getUserInfo(getParams):
	# Lib / validUser cookie present, just need their name
	# anonymous call
	try:

		username=getParams['username'][0]
		password=""


		# set ldap location, protocol version, and referrals
		l = ldap.initialize("ldap://directory.wayne.edu:389")
		l.protocol_version = ldap.VERSION3
		l.set_option(ldap.OPT_REFERRALS, 0)

		# test
		# when testing using library account, change searchFiler = "uid" to "cn"
		submitted_username = username
		username = "uid="+submitted_username+",ou=People,DC=wayne,DC=edu"
		password = password
		try:
			l.bind_s(username, password)
		except:
			jsonString = '{"desc":"Cannot bind username and password"}'
		
		# set baseDN, scope (SUBTREE searches searches for user and children), attributes
		baseDN = "dc=wayne,dc=edu"
		searchScope = ldap.SCOPE_SUBTREE
		retrieveAttributes = ['firstDotLast','givenName','uid']
		searchFilter = "uid="+submitted_username

		try:
			ldap_result_id = l.search(baseDN, searchScope, searchFilter, retrieveAttributes)
			result_set = list()
			result_type, result_data = l.result(ldap_result_id)
			if not result_data:
				jsonString = '{"desc":"not a valid User"}'
			else:
				for data in result_data:
					if data[0]:
						result_set.append(data)
						jsonString = json.dumps(result_set)		
		except ldap.LDAPError, e:
			jsonString = json.dumps(e.message)

	except:
		jsonString = '{"desc":"unsucessful"}'
	return jsonString


def objBitStreamTokens(getParams):
# function to accept a pid and bitStream key, and return bitStream tokenized URLs for download
######################################################################################################################	
	# check authentication with cookieAuth()
	print "checking user auth..."
	user_auth = cookieAuth(getParams)

	# if user is logged in and present in Ouroboros user table, return bitStream download tokens
	user_auth = json.loads(user_auth)
	username = getParams['username'][0]
	user_ouroboros = models.User.get(username)
	if user_auth['hashMatch'] and user_ouroboros:
		print "generating bitStream token dictionary"
		try:
			return json.dumps(BitStream.genAllTokens(getParams['PID'][0], BITSTREAM_KEY))
		except:
			return json.dumps({
						"status":False,
						"msg":"an error was had generating tokens"	
					})
	else:
		return json.dumps({
			"status":False,
			"msg":"user not authorized for bitStream tokenized URLs"	
		})




#######################################################################################################################
# --------------------------------------------------------------------------------------------------------------------#
# GENERAL / MISC / MIXED                                                                                              #
# --------------------------------------------------------------------------------------------------------------------#
#######################################################################################################################

def reportProb(getParams):
	'''
	This function accepts a PID as provided on the Digital Collections front-end and adds the object to a general holding list in Ouroboros

	Returns Dictionary containing Boolean value
	'''

	try:
		PID = getParams['PID'][0]
		form_notes = getParams['notes'][0]
		problemPID = models.user_pids(PID,"problemBot",1,"userReportedPIDs",form_notes)
		db.session.add(problemPID)
		db.session.commit()
		jsonString = '{"msg":"True"}'
	except:
		jsonString = '{"msg":"False"}'

	return jsonString

def addProbNote(getParams):
	'''
	This function accepts a PID as provided on the Digital Collections front-end and adds a note to the notes field

	Returns Dictionary containing Boolean value
	'''

	try:
		PID = getParams['PID'][0]
		form_notes = getParams['notes'][0]
		problemPID = models.user_pids.query.filter_by(PID=PID).order_by(models.user_pids.id.desc()).first()
		problemPID.notes = form_notes
		db.session.commit()
		jsonString = '{"msg":"True"}'
	except:
		jsonString = '{"msg":"False"}'

	return jsonString

def objectLoci(getParams):
	'''
	This function returns the intellectual organization and location of a WSUDOR object.

	Collection Siblings
		- uses objectCollectionIndex

	Search / Browse siblings
		- expects search parameters and window size, creates new search parameters

	results:
		collection1: -5 -4 -3 -2 -1 object 1 2 3 4 5
		collection2: -5 -4 -3 -2 -1 object 1 2 3 4 5
		search / browse: -5 -4 -3 -2 -1 object 1 2 3 4 5			
	'''	

	# config
	try:
		windowSize = int(getParams['windowSize'][0])
	except:
		windowSize = 30

	# get PID, context
	PID = getParams['PID'][0]		
	try:
		loci_context = getParams['loci_context'][0]
	except:
		loci_context = "nonsearch"
	print "Operating on PID:",PID,"loci_context is",loci_context

	# get fed handle 
	obj_ohandle = fedora_handle.get_object(PID)

	# only if object exists
	if obj_ohandle.exists == True:

		return_dict = {}

		# collection loci
		# retrieve COLLINDEX JSON		
		DS_handle = obj_ohandle.getDatastreamObject("COLLINDEX")

		# append collection information
		if DS_handle.exists == True:			
			COLLINDEX_JSON = DS_handle.content
			collection_index_dict = json.loads(COLLINDEX_JSON)

			for collection in collection_index_dict:				

				# perform solr query, get before and after
				collection_PID_suffix = collection.split(":")[1]	
				index = collection_index_dict[collection]['index']
				
				# bottom-out start for small index
				if (index - windowSize) < 0:
					start = 0
				else:
					start = index - windowSize

				# construct query string
				query = {
					"q" : "rels_isMemberOfCollection:*%s" % (collection_PID_suffix),
					"rows" : ((windowSize * 2) + 1),
					"start" : start,
					"sort" : "id asc"
				}				

				# perform query
				results = solr_handle.search(**query)	
				print "Collection index / total:",index,"/",results.total_results	
				results_list = results.documents

				# only one...	
				if results.total_results == 1:
					search_index_dict['previous_objects'] = []
					search_index_dict['next_objects'] = []
					
				# towards the beginning...
				elif index < windowSize:					
					collection_index_dict[collection]['previous_objects'] = [ results_list[i]['id'] for i in range(0,(index-1)) ]
					if (index+1)+windowSize > len(results_list):
						upperBound = len(results_list)
					else:
						upperBound = (index+1)+windowSize
					collection_index_dict[collection]['next_objects'] = [ results_list[i]['id'] for i in range((index+1),upperBound) ]

				# towards the end...
				elif (results.total_results - index ) < 6:
					wedge = index + 1					
					collection_index_dict[collection]['previous_objects'] = [ results_list[i]['id'] for i in range(0,windowSize) ]
					collection_index_dict[collection]['next_objects'] = [ results_list[i]['id'] for i in range(6,len(results_list)) ]					

				# solidly in the middle...
				else:					
					# grab previous / next, mid-collection					
					collection_index_dict[collection]['previous_objects'] = [ results_list[i]['id'] for i in range(0,windowSize) ]
					if (windowSize*2) + 1 > len(results_list):
						upperBound = len(results_list)
					else:
						upperBound = (windowSize*2) + 1
					collection_index_dict[collection]['next_objects'] = [ results_list[i]['id'] for i in range( (windowSize+1), upperBound ) ]
				

			#append to return_dict			
			return_dict['collection_loci'] = collection_index_dict
			print "Collection objectLoci added."


		# if "search" loci_context, access search parameters and search index, recreate, and return index in search
		if loci_context == "search":	

			# instantiate
			search_index_dict = {}			
			
			# get search and index params
			search_params = getParams['search_params'][0] # no zero needed, came in as object		
			search_index = getParams['search_index'][0]
			# print "search_params:",search_params," / search_index:",search_index			

			# convert to dictionary
			search_params = json.loads(search_params)

			# determine index in search
			index = int(search_params['start']) + int(search_index)			
			search_index_dict['index'] = index

			# construct new query
			# bottom-out start for small index
			if (index - windowSize) < 0:
				start = 0
			else:
				start = index - windowSize
			search_params['rows'] = (windowSize * 2) + 1
			search_params['start'] = start

			# perform query
			r = requests.get("http://localhost/%s?functions[]=solrSearch" % (getParams['API_url'][0]))
			solr_response_dict = json.loads(r.content)
			results_list = solr_response_dict['solrSearch']['response']['docs']
			numFound = int(solr_response_dict['solrSearch']['response']['numFound'])

			#debug
			print "Index / numFound:",index,"/",numFound
				
			# only one...	
			if numFound == 1:
				search_index_dict['previous_objects'] = []
				search_index_dict['next_objects'] = []

			# towards the beginning...
			elif index < windowSize:					
				search_index_dict['previous_objects'] = [ results_list[i]['id'] for i in range(0,index) ]
				if index + 1 + windowSize > len(results_list):
					upperBound = len(results_list)					
				else:
					upperBound = index + 1 + windowSize					
				search_index_dict['next_objects'] = [ results_list[i]['id'] for i in range((index+1),upperBound) ]

			# towards the end...
			elif (results.total_results - index ) < 6:
				wedge = index + 1					
				search_index_dict['previous_objects'] = [ results_list[i]['id'] for i in range(0,windowSize) ]
				search_index_dict['next_objects'] = [ results_list[i]['id'] for i in range(6,len(results_list)) ]					

			# solidly in the middle...
			else:				
				search_index_dict['previous_objects'] = [ results_list[i]['id'] for i in range(0,windowSize) ]
				if (windowSize * 2) + 1 > len(results_list):
					upperBound = len(results_list)
				else:
					upperBound = (windowSize*2) + 1					
				search_index_dict['next_objects'] = [ results_list[i]['id'] for i in range( (windowSize+1), upperBound ) ]

			#append to return_dict
			return_dict['search_loci'] = search_index_dict			

	else:
		return json.dumps({"msg":"that object id does not appear to exist"})
	
	return json.dumps(return_dict)



def saveSearch(getParams):
	'''
	This function saves the parameters from a DC front-end search (Solr) for reuse later
	'''

	return json.dumps({"status":"in progress"})



# function to return mimetypes, file extensions, or dictionary
def mimetypeDictionary(getParams):
	'''
	function to return mimetypes, file extensions, or dictionary

	two "direction" dicitonaries:
		mime2extension
		extension2mime

	option to filter with "inputFilter":
		= "extension"
		= "mime"

	notes:
	flip dictionary - inv_map = {v: k for k, v in map.items()}
	'''

	# # MOVE TO SOMEWHERE CENTRAL
	# ###########################################################################################
	# # import WSUDOR opinionated mimes
	# opinionated_mimes = {
	# 	# images
	# 	"image/jp2":".jp2"		
	# }	

	# # push to mimetypes.types_map
	# for k, v in opinionated_mimes.items():
	# 	# reversed here
	# 	mimetypes.types_map[v] = k
	# ###########################################################################################

	# grab requisite parameters		
	try:
		direction = getParams['direction'][0]
		if direction != "DS2extension":
			inputFilter = getParams['inputFilter'][0]
	except:
		return json.dumps({"status":"Parameters incorrect. Requires 'direction' parameter ('mime2extension' to return extension from mime, 'extension2mime' for mime from extension, or 'DS2extension' for file extension from WSUDOR object datastream), and 'inputFilter' parameter ('all', mimetype, or file extension) when direction is NOT 'DS2extension'."})

	# return file extension based on WSUDOR Datastream mimetype
	if direction == "DS2extension":		
		input_mimetype = fedora_handle.get_object(getParams['PID'][0]).getDatastreamObject(getParams['DS'][0]).mimetype
		return_string = mimetypes.guess_extension(input_mimetype)
		return json.dumps({"extension":return_string,"input_mimetype":input_mimetype})

	# return straight dictionary
	elif inputFilter == "all":
		if direction == "mime2extension":
			# flip mimetypes.types_map
			flipped = {v: k for k, v in mimetypes.types_map.items()}
			return json.dumps(flipped)
		if direction == "extension2mime":			
			return json.dumps(mimetypes.types_map)	

	# return file extension
	elif direction == "mime2extension":
		if "multiple" in getParams and getParams['multiple'][0] == "true":
			return_string = mimetypes.guess_all_extensions(inputFilter)
		else:
			return_string = mimetypes.guess_extension(inputFilter)
		return json.dumps(return_string)

	# return mimetype
	elif direction == "extension2mime":
		if not inputFilter.startswith('.'):
			inputFilter = "."+inputFilter
		try:
			return_string = mimetypes.types_map[inputFilter]
		except:
			return_string = "%s not found" % (inputFilter)
		return json.dumps(return_string)


	else:
		return json.dumps({"status":"Parameters incorrect. Requires 'direction' parameter ('mime2extension' to return extension from mime, 'extension2mime' for mime from extension) and 'inputFilter' parameter ('all', known mimetype, or known file extension).  Optional parameter, 'multiple=true' will return multiple file extensions for a given mimetype."})


















