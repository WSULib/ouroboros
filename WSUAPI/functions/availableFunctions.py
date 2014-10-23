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

# Fedora and Risearch imports
from fedDataSpy import checkSymlink

# Solr imports
import sunburnt

# utilities
from utils import *

# config
from localConfig import *

# modules from fedoraManager2
from fedoraManager2.fedoraHandles import fedora_handle
from fedoraManager2.solrHandles import solr_handle


'''
Description: This file represents all functions available to the WSUAPI.  

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
	PID=getParams['PID'][0]
	PID = PID.replace(":", "\:")
	baseURL = "http://silo.lib.wayne.edu/solr4/search/select?"
	solrParams = {
		'q' : 'id:{PID}'.format(PID=PID),
		'wt' : 'json',
		'fl' : 'id mods* dc* rels* obj* facet* last_modified' # throttled to prevent unwanted fields from weighing down response		
	}
	r = requests.get(baseURL , params=solrParams)			
	jsonString = r.text
	return jsonString


def solrSearch(getParams):
######################################################################################################################	
	# establish baseURL
	if 'solrCore' in getParams:				
		baseURL = "http://silo.lib.wayne.edu/solr4/{solrCore}/select?".format(solrCore=getParams['solrCore'][0])
	else:
		baseURL = "http://silo.lib.wayne.edu/solr4/search/select?"	

	# hard-code some server side parameters	
	# sorts date result 
	getParams['f.dc_date.facet.sort'] = ["index"]
	# no limit on facets
	getParams['facet.limit'] = ["-1"]
	# implies "AND" operator for all blank spaces when q.op not explicitly set
	if 'q.op' not in getParams:
		getParams['q.op'] = ["AND"]	

	# q
	if 'q' in getParams:	
		# escape colons in query string if "noescape" not set	
		if 'raw' in getParams and getParams['raw'] == "escapeterms":
			qfront = getParams['q'][0].split(":",1)[0]			
			qtail = getParams['q'][0].split(":",1)[1].replace(":","\:")			
			getParams['q'][0] = qfront+":"+qtail

		elif 'raw' not in getParams or getParams['raw'][0] != "noescape":																		
			getParams['q'][0] = escapeSolrArg(getParams['q'][0])			
	else:
		print "*No search terms provided*"
		getParams['q'][0] = ""
	# add to URL
	baseURL	+= "q="+getParams['q'][0]+"&"

	## BACKDOOR FOR VIEWING ALL ITEMS, NOT JUST isDiscoverableTrue	
	if 'fullView' in getParams and getParams['fullView'][0] == "fullview123456789":
		pass
	else:
		baseURL	+= "fq=rels_isDiscoverable:True&"

	# facets
	if 'facets[]' in getParams:
		for facet in getParams['facets[]']:
			baseURL += ("facet.field="+facet+"&")	

	# filter queries
	if "fq[]" in getParams:
		for fq in getParams['fq[]']:
			baseURL += ("fq="+fq+"&")	

	# tack on fl
	baseURL += "&fl=id mods* dc* rels* obj* last_modified&"	

	processed = ["raw","fullview","facets[]","fq[]","q"]

	# add all other parameters	
	for k in getParams:
		if k not in processed:
			baseURL += (k+"="+str(getParams[k][0])+"&")		

	# make Solr Request
	r = requests.get(baseURL)			
	jsonString = r.text	
	return jsonString


def solrCoreGeneric(getParams):
######################################################################################################################	
	# print getParams

	# establish baseURL
	if 'solrCore' in getParams:				
		baseURL = "http://silo.lib.wayne.edu/solr4/{solrCore}/select?".format(solrCore=getParams['solrCore'][0])
	else:
		baseURL = "http://silo.lib.wayne.edu/solr4/search/select?"		

	# q
	if 'q' in getParams:	
		# escape colons in query string if "noescape" not set	
		if 'raw' in getParams and getParams['raw'] == "escapeterms":
			qfront = getParams['q'][0].split(":",1)[0]			
			qtail = getParams['q'][0].split(":",1)[1].replace(":","\:")			
			getParams['q'][0] = qfront+":"+qtail
		elif 'raw' not in getParams or getParams['raw'][0] != "noescape":																		
			getParams['q'][0] = escapeSolrArg(getParams['q'][0])			
	else:
		print "*No search terms provided*"
		getParams['q'][0] = ""

	# add to URL
	baseURL	+= "q="+getParams['q'][0]+"&"	

	# facets
	if 'facets[]' in getParams:
		for facet in getParams['facets[]']:
			baseURL += ("facet.field="+facet+"&")	

	# filter queries
	if "fq[]" in getParams:
		for fq in getParams['fq[]']:
			baseURL += ("fq="+fq+"&")

	processed = ["raw","fullview","facets[]","fq[]","q"]

	# add all other parameters	
	for k in getParams:
		if k not in processed:
			baseURL += (k+"="+str(getParams[k][0])+"&")		

	# make Solr Request
	r = requests.get(baseURL)			
	jsonString = r.text	
	return jsonString


def solrFacetSearch(getParams):
######################################################################################################################
	# establish baseURL
	baseURL = "http://silo.lib.wayne.edu/solr4/search/select?"

	# set solrParams
	solrParams = ast.literal_eval(getParams['solrParams'][0])
	solrParams["wt"] = "python"	
	print "Solr Search Params:", solrParams

	# Solr Terms Parsing
	# BAD LOGIC.  REDO.
	if 'q' in solrParams:	
		# escape colons in query string if "noescape" not set	
		if 'raw' in solrParams and solrParams['raw'] == "escapeterms":
			qfront = solrParams['q'].split(":",1)[0]
			qtail = solrParams['q'].split(":",1)[1].replace(":","\:")
			solrParams['q'] = qfront+":"+qtail

		elif 'raw' not in solrParams or solrParams['raw'] != "noqescape":		
			solrParams['q'] = escapeSolrArg(solrParams['q'])
	else:
		print "*No search terms provided*"
		solrParams['q'] = ""

	## Show only items with rels_isSearchable = True	
	if 'fullView' in solrParams and solrParams['fullView'] == "on":
		pass
	else:
		baseURL	+= "fq=rels_isDiscoverable:True&"

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

	# create cleaned up dictionary
	print r.text
	tempDict = ast.literal_eval(r.text)
	facetFieldsList = tempDict["facet_counts"]["facet_fields"]["rels_isMemberOfCollection"]
	prettyDict = {}
	i = 0
	while i < len(facetFieldsList):
		prettyDict[facetFieldsList[i]] = facetFieldsList[(i+1)]
		i+=2
	print prettyDict

	jsonString = json.dumps(prettyDict)

	return jsonString


def getUserFavorites(getParams):
######################################################################################################################

	# establish baseURL
	baseURL = "http://silo.lib.wayne.edu/solr4/users/select?"

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


def userSearch(getParams):
######################################################################################################################

	# establish baseURL
	baseURL = "http://silo.lib.wayne.edu/solr4/users/select?"

	solrParams = {}
	solrParams['q'] = 'id:'+getParams['username'][0]
	solrParams["wt"] = "python"	

	# add all other parameters	
	for k in solrParams:		
		baseURL += (k+"="+str(solrParams[k])+"&")	

	## DEBUG
	print "\n\n***SOLR PARAMS***",solrParams
	print "\n\n***BASE URL***",baseURL,"\n\n"

	# make Solr Request, save to userDict
	r = requests.get(baseURL)				
	userDict = ast.literal_eval(r.text)
	print userDict

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

	print userReturnDict
	jsonString = json.dumps(userReturnDict)

	return jsonString



def WSUDORuserAuth(getParams):
######################################################################################################################

	# expectimg username, clientHash
	# get hash for username from solr (don't need password), compare

	# establish baseURL
	baseURL = "http://silo.lib.wayne.edu/solr4/users/select?"
	# print "Here's what we have to authorize with in WSUDOR..."
	# print getParams

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
	baseURL = "http://silo.lib.wayne.edu/solr4/users/select?"
	# print "Params for cookieAuth"
	# print getParams

	# check for clientHash
	if 'clientHash' not in getParams:
		print "account hasshes do NOT match."
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
		# print "account hashes match"
		userReturnDict['hashMatch'] = True
	else:
		# print "account hasshes do NOT match."
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

	baseURL = "http://silo.lib.wayne.edu/solr4/users/update/json?commit=true"
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

	baseURL = "http://silo.lib.wayne.edu/solr4/users/update/json?commit=true"
	headersDict = {
		"Content-type":"application/json"
	}

	r = requests.post(baseURL, data=solrString, headers=headersDict)
	jsonString = r.text
	return jsonString


def removeFavorite(getParams):
# function to take jsonAddString, remove from Solr, and return confirmation code
######################################################################################################################	
	returnDict = {}

	# authenticate user	
	username = getParams['username'][0]
	providedHash = getParams['userhash'][0]

	si = sunburnt.SolrInterface("http://silo.lib.wayne.edu:8080/solr4/users/")	
	response = si.query(user_username=username).execute()
	recordedHash = response[0]['user_hash'][0]
	# print "Provided:",providedHash
	# print "Recorded:",recordedHash
	if providedHash == recordedHash:
		# print "Credentials look good, proceeding."
		# delete doc
		PID = getParams['PID'][0]
		si.delete(username+"_"+PID)
		si.commit()

		# return response
		returnDict['username'] = username
		returnDict['favorite_removed'] = PID
		return json.dumps(returnDict)

	else:
		# print "Credentials don't match."
		returnDict['status'] = "Credentials don't match."
		return json.dumps(returnDict)



def solrTranslationHash(args):
# function to return PIDs and their Labels in JS Hash that can / is used to cleanup front-end interfaces, 
# and interact with things in meaningful ways
# Note: Makes sense to key off PID however for logic, as these are less likely to change than the Object Label / DC Title field
######################################################################################################################	


	# list of queries to translate results
	queriesToTrans = [
		# all Collection objects
		"http://silo.lib.wayne.edu/solr4/search/select?q=rels_hasContentModel%3Ainfo%5C%3Afedora%2FCM%5C%3ACollection&fl=id+dc_title&wt=json&indent=true&rows=100",
		# all Content Models Types
		"http://silo.lib.wayne.edu/solr4/search/select?q=id%3ACM*&rows=100&fl=id+dc_title&wt=json&indent=true&rows=100"
	]

	# run query and add to hash
	transDict = {}
	for query in queriesToTrans:
		r = requests.get(query)
		tempDict = ast.literal_eval(r.text)['response']['docs']
		for each in tempDict:
			transDict[("info:fedora/"+each['id'])] = each['dc_title'][0]

	# churn to JSON and return
	transJSONpackage = json.dumps(transDict)
	return transJSONpackage


# experiemtnal function to query and update /pubstore core in Solr4.
# this core is used as a quasi-datastore at this point, perhaps exclusively for ephemeral data
def pubStore(getParams):
	urlsuff = getParams['urlsuff'][0]
	solrString = getParams['json'][0]	

	# print solrString

	baseURL = "http://silo.lib.wayne.edu/solr4/pubstore/{urlsuff}".format(urlsuff=urlsuff)
	# baseURL = "http://silo.lib.wayne.edu/solr4/pubstore/update/json?commit=true"
	# print "Going to this URL:",baseURL

	# json post
	if "update" in urlsuff:
		headersDict = {
			"Content-type":"application/json"
		}

		r = requests.post(baseURL, data=solrString, headers=headersDict)

	# get
	if "select" in urlsuff:
		solrParams = ast.literal_eval(solrString)
		print "Is this a dictionary?",solrParams		
		r = requests.get(baseURL, params=solrParams)

	jsonString = r.text
	return jsonString




#######################################################################################################################
# --------------------------------------------------------------------------------------------------------------------#
# FEDORA RELATED                                                                                                      #
# --------------------------------------------------------------------------------------------------------------------#
#######################################################################################################################

# return Fedora MODS datastream
def getObjectXML(getParams):	
	baseURL = "http://silo.lib.wayne.edu/fedora/objects/{PID}/objectXML".format(PID=getParams['PID'][0])
	r = requests.get(baseURL, auth=(FEDORA_USER, FEDORA_PASSWORD))			
	xmlString = r.text

	#check if valid PID
	if xmlString.startswith("Object not found in low-level storage:"):
		outputDict = {"object_status" : 'Absent' }
	else:
		#convert XML to JSON with "xmltodict"
		xmlDict = xmltodict.parse(xmlString)	
		objectStatus = xmlDict['foxml:digitalObject']['foxml:objectProperties']['foxml:property'][0]['@VALUE']
		outputDict = {"object_status" : objectStatus }

	output = json.dumps(outputDict)
	return output


# gets children for single PID
def isMemberOf(getParams):

	baseURL = "http://silo.lib.wayne.edu/fedora/risearch"
	risearch_query = "select $subject from <#ri> where <info:fedora/{PID}> <info:fedora/fedora-system:def/relations-external#isMemberOf> $subject".format(PID=getParams['PID'][0])
	risearch_params = {
	'type': 'tuples',
	'lang': 'itql',
	'format': 'json',
	'limit':'',
	'dt': 'on',
	'query': risearch_query
	}

	r = requests.post(baseURL, auth=(FEDORA_USER, FEDORA_PASSWORD), data=risearch_params)
	# strip risearch namespace "info:fedora"
	jsonString = r.text.replace('info:fedora/','')			
	return jsonString

# get isMemberOf children for single PID
def hasMemberOf(getParams):	
	baseURL = "http://silo.lib.wayne.edu/fedora/risearch"
	risearch_query = "select $memberTitle $object from <#ri> where $object <info:fedora/fedora-system:def/relations-external#isMemberOf> <info:fedora/{PID}> and $object <http://purl.org/dc/elements/1.1/title> $memberTitle order by $memberTitle".format(PID=getParams['PID'][0])
	risearch_params = {
	'type': 'tuples',
	'lang': 'itql',
	'format': 'json',
	'limit':'',
	'dt': 'on',
	'query': risearch_query
	}

	r = requests.post(baseURL, auth=(FEDORA_USER, FEDORA_PASSWORD), data=risearch_params)
	# strip risearch namespace "info:fedora"
	jsonString = r.text.replace('info:fedora/','')			
	return jsonString

# get parents for PID
def isMemberOfCollection(getParams):

	baseURL = "http://silo.lib.wayne.edu/fedora/risearch"
	# risearch_query = "select $subject from <#ri> where <info:fedora/{PID}> <info:fedora/fedora-system:def/relations-external#isMemberOfCollection> $subject".format(PID=args.PID)
	risearch_query = "select $collectionTitle $subject from <#ri> where <info:fedora/{PID}> <info:fedora/fedora-system:def/relations-external#isMemberOfCollection> $subject and $subject <http://purl.org/dc/elements/1.1/title> $collectionTitle".format(PID=getParams['PID'][0])

	risearch_params = {
	'type': 'tuples',
	'lang': 'itql',
	'format': 'json',
	'limit':'',
	'dt': 'on',
	'query': risearch_query
	}

	r = requests.post(baseURL, auth=(FEDORA_USER, FEDORA_PASSWORD), data=risearch_params)
	# strip risearch namespace "info:fedora"
	jsonString = r.text.replace('info:fedora/','')
	return jsonString

# get isMemberOf children for single PID
def hasMemberOfCollection(getParams):	
	baseURL = "http://silo.lib.wayne.edu/fedora/risearch"
	risearch_query = "select $memberTitle $object from <#ri> where $object <info:fedora/fedora-system:def/relations-external#isMemberOfCollection> <info:fedora/{PID}> and $object <http://purl.org/dc/elements/1.1/title> $memberTitle order by $memberTitle".format(PID=getParams['PID'][0])
	risearch_params = {
	'type': 'tuples',
	'lang': 'itql',
	'format': 'json',
	'limit':'',
	'dt': 'on',
	'query': risearch_query
	}

	r = requests.post(baseURL, auth=(FEDORA_USER, FEDORA_PASSWORD), data=risearch_params)
	# strip risearch namespace "info:fedora"
	jsonString = r.text.replace('info:fedora/','')			
	return jsonString


#returns all siblings, from all parent Collections
def getSiblings(getParams):
	baseURL = "http://silo.lib.wayne.edu/fedora/risearch"
	risearch_query = "select $collection $sibling from <#ri> where <info:fedora/{PID}> <info:fedora/fedora-system:def/relations-external#isMemberOfCollection> $collection and $sibling <info:fedora/fedora-system:def/relations-external#isMemberOfCollection> $collection".format(PID=getParams['PID'][0])
	risearch_params = {
	'type': 'tuples',
	'lang': 'itql',
	'format': 'csv',
	'limit':'',
	'dt': 'on',
	'query': risearch_query
	}

	# prepare as JSON dict
	r = requests.post(baseURL, auth=(FEDORA_USER, FEDORA_PASSWORD), data=risearch_params)
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
	baseURL = "http://silo.lib.wayne.edu/fedora/objects/{PID}/datastreams/MODS/content".format(PID=getParams['PID'][0])
	r = requests.get(baseURL, auth=(FEDORA_USER, FEDORA_PASSWORD))			
	xmlString = r.text
	#convert XML to JSON with "xmltodict"
	outputDict = xmltodict.parse(xmlString)
	output = json.dumps(outputDict)
	return output


# return walk of serial volumes / issues in tidy package
def serialWalk(getParams):
	baseURL = "http://silo.lib.wayne.edu/fedora/risearch"
	risearch_query = "SELECT ?volume ?volumeTitle ?issue $issueTitle WHERE {{ ?volume  <fedora-rels-ext:isMemberOfCollection> <info:fedora/{PID}> .  $volume <http://purl.org/dc/elements/1.1/title> ?volumeTitle . ?volume  <fedora-rels-ext:hasContentModel> <info:fedora/CM:Volume> . ?issue <fedora-rels-ext:isMemberOf>  ?volume . ?issue <fedora-rels-ext:hasContentModel> <info:fedora/CM:Issue> . $issue <http://purl.org/dc/elements/1.1/title> $issueTitle .  }} ORDER BY ASC(?issue)".format(PID=getParams['PID'][0])
	risearch_params = {
		'type': 'tuples',
		'lang': 'sparql',
		'format': 'json',
		'limit':'',
		'dt': 'on',
		'query': risearch_query
	}

	r = requests.post(baseURL, auth=(FEDORA_USER, FEDORA_PASSWORD), data=risearch_params)
	# strip risearch namespace "info:fedora"
	jsonString = r.text.replace('info:fedora/','')			
	return jsonString


# return symlink (created or retrieved) to object in datastreamStore
def fedDataSpy(getParams):

	outputDict = {}
	PID = getParams['PID'][0]
	DS = getParams['DS'][0]	
	outputDict = checkSymlink(PID,DS)

	jsonString = json.dumps(outputDict)
	return jsonString



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
	returns the metadata for a single object, from Solr, via the WSUAPI
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



# Search / Browse / Collections
################################################################################################
def solrSearchCollectionObjects(getParams):
	'''
	returns results for all collection objects, from Solr, via the WSUAPI
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




#######################################################################################################################
# --------------------------------------------------------------------------------------------------------------------#
# LDAP / USER AUTHENTICATION                                                                                          #
# --------------------------------------------------------------------------------------------------------------------#
#######################################################################################################################

def authUser(getParams):
	try:

		username=getParams['username'][0]
		password=getParams['password'][0]

		returnDict = {}

		###############################################################
		# get clientHash# 
		try:
			userDict = {}
			baseURL = "http://silo.lib.wayne.edu/solr4/users/select?"
			
			solrParams = {}
			solrParams['q'] = 'id:'+username
			solrParams["wt"] = "python"
			# add all other parameters	
			for k in solrParams:		
				baseURL += (k+"="+str(solrParams[k])+"&")	

			# make Solr Request, save to userDict
			r = requests.get(baseURL)				
			userDict = ast.literal_eval(r.text)
			print "\n\n\n"
			print "Results of clientHash retrieval from LDAP authorization:"
			print userDict['response']['docs'][0]['user_hash'][0]			
			print "\n\n\n"
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
			print returnDict
			jsonString = json.dumps(returnDict)
			################################################
			return jsonString
		except ldap.LDAPError, e:
			jsonString = json.dumps(e.message)
			return jsonString

	except:
		jsonString = '{"desc":"unsucessful"}'
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




#######################################################################################################################
# --------------------------------------------------------------------------------------------------------------------#
# GENERAL / MISC / MIXED                                                                                                     #
# --------------------------------------------------------------------------------------------------------------------#
#######################################################################################################################

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

	# get PID, context
	PID = getParams['PID'][0]		
	try:
		loci_context = getParams['loci_context'][0]
	except:
		loci_context = "nonsearch"
	print "Operating on PID:",PID,"loci_context is",loci_context

	# get fed handle 
	obj_ohandle = fedora_handle.get_object(PID)

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
				if (index - 5) < 0:
					start = 0
				else:
					start = index - 5

				# construct query string
				query = {
					"q" : "rels_isMemberOfCollection:*{collection_PID_suffix}".format(collection_PID_suffix=collection_PID_suffix),
					"rows" : 11,
					"start" : start,
					"sort" : "id asc"
				}				

				# perform query
				results = solr_handle.search(**query)	
				print "index / total",index,"/",results.total_results	
				results_list = results.documents
					
				if index < 5:
					wedge = index + 1
					collection_index_dict[collection]['previous_objects'] = [ results_list[i]['id'] for i in range(0,index) ]
					collection_index_dict[collection]['next_objects'] = [ results_list[i]['id'] for i in range(wedge,(wedge+5)) ]

				elif (results.total_results - index ) < 6:
					wedge = index + 1					
					collection_index_dict[collection]['previous_objects'] = [ results_list[i]['id'] for i in range(0,5) ]
					collection_index_dict[collection]['next_objects'] = [ results_list[i]['id'] for i in range(6,len(results_list)) ]					

				else:
					# grab previous / next, mid-collection
					collection_index_dict[collection]['previous_objects'] = [ results_list[i]['id'] for i in range(0,5) ]				
					collection_index_dict[collection]['next_objects'] = [ results_list[i]['id'] for i in range(6,11) ]
				

			#append to return_dict
			print "Collection dict:",collection_index_dict
			return_dict['collection_loci'] = collection_index_dict


		# if "search" loci_context, access search parameters and search index, recreate, and return index in search
		if loci_context == "search":	

			# instantiate
			search_index_dict = {}			
			
			# get search and index params
			search_params = getParams['search_params'][0] # no zero needed, came in as object		
			search_index = getParams['search_index'][0]
			print "search_params:",search_params," / search_index:",search_index			

			# convert to dictionary
			search_params = json.loads(search_params)		

			# determine index in search
			index = int(search_params['start']) + int(search_index)			
			search_index_dict['index'] = index

			# construct new query
			# bottom-out start for small index
			if (index - 5) < 0:
				start = 0
			else:
				start = index - 5
			search_params['rows'] = 11
			search_params['start'] = start

			# perform query
			r = requests.get("http://localhost/{API_url}?functions[]=solrSearch".format(API_url=getParams['API_url'][0]),params=search_params)
			solr_response_dict = json.loads(r.content)
			results_list = solr_response_dict['solrSearch']['response']['docs']
			numFound = int(solr_response_dict['solrSearch']['response']['numFound'])
					
			if numFound == 1:
				search_index_dict['previous_objects'] = []
				search_index_dict['next_objects'] = []

			elif index < 5:
				wedge = index + 1
				search_index_dict['previous_objects'] = [ results_list[i]['id'] for i in range(0,index) ]
				search_index_dict['next_objects'] = [ results_list[i]['id'] for i in range(wedge,(wedge+5)) ]

			elif ( numFound - index ) < 6:
				wedge = index + 1					
				search_index_dict['previous_objects'] = [ results_list[i]['id'] for i in range(0,5) ]
				search_index_dict['next_objects'] = [ results_list[i]['id'] for i in range(6,len(results_list)) ]					

			else:
				# grab previous / next, mid-collection
				search_index_dict['previous_objects'] = [ results_list[i]['id'] for i in range(0,5) ]				
				search_index_dict['next_objects'] = [ results_list[i]['id'] for i in range(6,11) ]

			#append to return_dict
			print "Search dict:",search_index_dict
			return_dict['search_loci'] = search_index_dict			

	else:
		return json.dumps({"msg":"that object id does not appear to exist"})
	
	return json.dumps(return_dict)



def saveSearch(getParams):
	'''
	This function saves the parameters from a DC front-end search (Solr) for reuse later
	'''

	return json.dumps({"status":"in progress"})





















