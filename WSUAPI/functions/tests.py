# Functions for testing System functionality
import requests
import json

# import functions from other API sections
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
def integrityTest(getParams):

	# create dictionary that will equate function / task with True / False and result message	
	resultsDict = {}

	# run functions here

	# return resultsDict as function response
	return json.dumps(resultsDict)

	

# INDIVIDUAL TEST FUNCTIONS
################################################################################################

# example...
def getSingleObjectSolrMetadata(getParams):
	# solr search	
	result = solr.solrGetFedDoc({"PID":["wayne:CFAIEB01a045"]})
	try:		
		json.loads(result) # tests JSON validity	
		return result # return JSON for API response
	except Exception, e:
		return json.dumps(e)


