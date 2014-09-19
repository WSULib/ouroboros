# Solr Functions
import requests
import ast
import urllib
from paste.util.multidict import MultiDict
import json
import re
import hashlib
from localConfig import *
from utils import *

# python sunburnt module
import sunburnt


def solrGetFedDoc(getParams):
#get title and everything from a SOLR request
######################################################################################################################
	PID=getParams['PID'][0]
	PID = PID.replace(":", "\:")
	baseURL = "http://localhost/solr4/search/select?"
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
		baseURL = "http://localhost/solr4/{solrCore}/select?".format(solrCore=getParams['solrCore'][0])
	else:
		baseURL = "http://localhost/solr4/search/select?"	

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
		baseURL = "http://localhost/solr4/{solrCore}/select?".format(solrCore=getParams['solrCore'][0])
	else:
		baseURL = "http://localhost/solr4/search/select?"		

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
	baseURL = "http://localhost/solr4/search/select?"

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
	baseURL = "http://localhost/solr4/users/select?"
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
	baseURL = "http://localhost/solr4/users/select?"
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


def removeFavorite(getParams):
# function to take jsonAddString, remove from Solr, and return confirmation code
######################################################################################################################	
	returnDict = {}

	# authenticate user	
	username = getParams['username'][0]
	providedHash = getParams['userhash'][0]

	si = sunburnt.SolrInterface("http://localhost:8080/solr4/users/")	
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
		"http://localhost/solr4/search/select?q=rels_hasContentModel%3Ainfo%5C%3Afedora%2FCM%5C%3ACollection&fl=id+dc_title&wt=json&indent=true&rows=100",
		# all Content Models Types
		"http://localhost/solr4/search/select?q=id%3ACM*&rows=100&fl=id+dc_title&wt=json&indent=true&rows=100"
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

	baseURL = "http://localhost/solr4/pubstore/{urlsuff}".format(urlsuff=urlsuff)
	# baseURL = "http://localhost/solr4/pubstore/update/json?commit=true"
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