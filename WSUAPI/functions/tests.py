# Functions for testing System functionality
import requests
import json
import subprocess

# import sibling files
import solr
import fedora


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
################################################################################################
def getItems():
	# return an array of PIDs from current collections
	pass



# ALL TEST
################################################################################################
# function for testing overall integrity of front-end system
# runs tests from below, integrating results into one JSON package, with True / False verdict
################################################################################################
def integrityTest(getParams):

	# create dictionary that will equate function / task with True / False and result message		
	resultsList = []	

	# run functions here
	#########################################################################################################################
	# Single Objects
	resultsList.append({"getSingleObjectSolrMetadata":json.loads(getSingleObjectSolrMetadata({"PID":"wayne:CFAIEB01a002"}))})
	# resultsList.append({"singleObjectPageRender":json.loads(singleObjectPageRender({"PID":"wayne:CFAIEB01a002"}))})
	
	# Search / Browse / Collections
	resultsList.append({"solrSearchKnownTerm":json.loads(solrSearchKnownTerm({"search_term":"Michigan"}))})
	resultsList.append({"solrSearchCollectionObjects":json.loads(solrSearchCollectionObjects({"search_term":"rels_hasContentModel%3Ainfo%5C%3Afedora%2FCM%5C%3ACollection"}))})
	# resultsList.append({"searchPageRender":json.loads(searchPageRender({"search_term":"Michigan"}))})
	# resultsList.append({"collectionPageRender":json.loads(collectionPageRender({False}))})
	#########################################################################################################################

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
################################################################################################



################################################################################################
# Single Objects
################################################################################################
def getSingleObjectSolrMetadata(getParams):
	'''
	returns the metadata for a single object, from Solr, via the WSUAPI
	SUCCESS: solr.response.docs > 0
	FAILURE: solr.response.docs == 0
	'''
	# solr search	
	result = solr.solrGetFedDoc({"PID":[getParams['PID']]})	
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
				'msg':"Response successful, but numFound wrong.  Should be 1, found {numFound}".format(numFound=str(numFound))
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
	URL = "http://digital.library.wayne.edu/digitalcollections/item?id={PID}".format(PID=PID)

	try:				
		http_status_string = subprocess.check_output("python WSUAPI/functions/ghostGetHttpStatus.py {URL}".format(URL=URL), shell=True)
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
				'msg':"Ghost.py rendering unsuccessful, HTTP status {http_status}.".format(http_status=str(http_status))
			}		
	
	except Exception, e:
		returnDict = {
			'result' : False,
			'msg' : json.dumps(e)
		}		

	print "Page Rendering:",returnDict

	return json.dumps(returnDict)




################################################################################################
# Search / Browse / Collections
################################################################################################
def solrSearchCollectionObjects(getParams):
	'''
	returns results for all collection objects, from Solr, via the WSUAPI
	SUCCESS: solr.response.docs > 0
	FAILURE: solr.response.docs == 0
	'''
	# solr search	

	result = solr.solrSearch({"q":[getParams['search_term']],"wt":["json"]})
	
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
				'msg':"Response successful, but numFound wrong.  Should be > 0, found {numFound}".format(numFound=str(numFound))
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
	returns results for word "Michigan", from Solr, via the WSUAPI
	SUCCESS: solr.response.docs > 0
	FAILURE: solr.response.docs == 0
	'''
	# solr search	

	result = solr.solrSearch({"q":[getParams['search_term']],"wt":["json"]})
	
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
				'msg':"Response successful, but numFound wrong.  Should be > 0, found {numFound}".format(numFound=str(numFound))
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
	URL = "http://digital.library.wayne.edu/digitalcollections/search.php?q={search_term}".format(search_term=getParams['search_term'])

	try:				
		http_status_string = subprocess.check_output("python WSUAPI/functions/ghostGetHttpStatus.py {URL}".format(URL=URL), shell=True)
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
				'msg':"Ghost.py rendering unsuccessful, HTTP status {http_status}.".format(http_status=str(http_status))
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
	URL = "http://digital.library.wayne.edu/digitalcollections/allcollections.php"

	try:				
		http_status_string = subprocess.check_output("python WSUAPI/functions/ghostGetHttpStatus.py {URL}".format(URL=URL), shell=True)
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
				'msg':"Ghost.py rendering unsuccessful, HTTP status {http_status}.".format(http_status=str(http_status))
			}		
	
	except Exception, e:
		returnDict = {
			'result' : False,
			'msg' : json.dumps(e)
		}		

	print "Page Rendering:",returnDict

	return json.dumps(returnDict)















































