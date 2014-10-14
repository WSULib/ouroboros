# Functions for testing System functionality
import requests
import json

# import sibling files
import solr
import fedora


'''
Brainstorming / Tests:
----------------------

+ we want to test the integrity of the system, not the integrity of the collection items (metadata, RELS-EXT, etc)
+ known items will be one from each collection
+ random items, don't want fales positives
+ each function returns JSON, with True or False
+ main integrityTest() function compiles these, all can be run independently

+ Can include "Best Guess" based on analysis of function results

+ For penultimate test, push all "True" and "False" results to resultsList[], then check if any Falses tehre
	if False in resultsList:
		then fail.

Want to test:
- linkages of Solr-WSUAPI
	- solr.solrGetFedDoc() 
	- fedora.getObjectXML()
	- linkages of search / browse
		- known search term, e.g. "Detroit" - solr.solrSearch()

- front-end page rendering
	- single object page redirect to 404 = front-end, Solr, or WSUAPI is malfunctioning (check page.url == http://digital.library.wayne.edu/dev/graham/digitalcollections/404.php)
	- collection page (?)
 	- search page (?)

- images
	- imageServer hit of known item PREVIEW and THUMBNAIL
'''


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
	resultsList.append(json.loads(getSingleObjectSolrMetadata(getParams)))

	# read all functions, determine if any false present
	for eachFunction in resultsList:	# json.loads
		final_verdict = True
		# eachFunction = json.loads(eachFunction)	
		if eachFunction['result'] == True:
			final_verdict = True
		elif eachFunction['result'] == False:
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



def getSingleObjectSolrMetadata(getParams):
	'''
	returns the metadata for a single object, from Solr, via the WSUAPI
	SUCCESS: solr.response.docs > 0
	FAILURE: solr.response.docs == 0
	'''
	# solr search	
	result = solr.solrGetFedDoc({"PID":["wayne:CFAIEB01a045-GIBBERISH"]})	
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


