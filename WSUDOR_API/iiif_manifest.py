# Ouroboros config
import localConfig

# python modules
import json

# flask proper
from flask import render_template, request, session, redirect, make_response, Response

# WSUDOR_API_app
from WSUDOR_API import cache
from WSUDOR_API import WSUDOR_API_app
import WSUDOR_ContentTypes
from WSUDOR_Manager import redisHandles
from functions.packagedFunctions import singleObjectPackage


# small function to skip caching, reads from localConfig.py
def skipCache():
	return localConfig.API_SKIP_CACHE


# IIIF_MANIFEST MAIN
#########################################################################################################
@WSUDOR_API_app.route("/%s/<identifier>" % (localConfig.IIIF_MANIFEST_PREFIX), methods=['POST', 'GET'])
def iiif_manifest(identifier):		

	'''
	While using fedora 3.x, we'll be sending the PID as the identifier
	'''

	getParams = {each:request.values.getlist(each) for each in request.values}

	try:
		# fire retrieveManifest
		response = make_response( retrieveManifest(identifier,getParams) )
		response.headers['Access-Control-Allow-Origin'] = '*'
		response.headers['Access-Control-Allow-Methods'] = 'GET, POST'
		response.headers['Access-Control-Allow-Headers'] = 'x-prototype-version,x-requested-with'
		response.headers['Access-Control-Max-Age'] = 2520
		response.headers["Content-Type"] = "application/json"		
		response.headers['X-Powered-By'] = 'ShoppingHorse'
		response.headers['Connection'] = 'Close'
		return response

	except Exception,e:
		print "WSUDOR_API iiif_manifest call unsuccessful.  Error:",str(e)
		return '{{"WSUDOR_APIstatus":"WSUDOR_API iiif_manifest call unsuccessful.","WSUDOR_APIstatus iiif_manifest message":%s}}' % (json.dumps(str(e)))
		

@cache.memoize(timeout=localConfig.API_CACHE_TIMEOUT, unless=skipCache)
def retrieveManifest(identifier,getParams):

	'''
	genIIIFManifest() is a function built-in to each content-type.
	In an effort to reduce how many times these manifests are generated, this function now tries
	to retreive from Redis first.  If not there, runs object method to generate, then tries again.
	'''
	
	# check Redis for manifest
	r_response = redisHandles.r_iiif.get(identifier)
	if r_response != None:
		print "manifest located and retrieved from Redis"
		return r_response
	else:
		print "generating manifest, storing in redis, returning"
		# open object_handle
		obj_handle = WSUDOR_ContentTypes.WSUDOR_Object(identifier)
		# fire content-type defined manifest generation
		return obj_handle.genIIIFManifest()
	








