# Main Fedora and Risearch querying module
import requests
import urllib
from localConfig import *
import xmltodict, json
from fedDataSpy import checkSymlink


# return Fedora MODS datastream
def getObjectXML(getParams):	
	baseURL = "http://localhost/fedora/objects/{PID}/objectXML".format(PID=getParams['PID'][0])
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

	baseURL = "http://localhost/fedora/risearch"
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
	baseURL = "http://localhost/fedora/risearch"
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

	baseURL = "http://localhost/fedora/risearch"
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
	baseURL = "http://localhost/fedora/risearch"
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
	baseURL = "http://localhost/fedora/risearch"
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
	baseURL = "http://localhost/fedora/objects/{PID}/datastreams/MODS/content".format(PID=getParams['PID'][0])
	r = requests.get(baseURL, auth=(FEDORA_USER, FEDORA_PASSWORD))			
	xmlString = r.text
	#convert XML to JSON with "xmltodict"
	outputDict = xmltodict.parse(xmlString)
	output = json.dumps(outputDict)
	return output


# return walk of serial volumes / issues in tidy package
def serialWalk(getParams):
	baseURL = "http://localhost/fedora/risearch"
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












