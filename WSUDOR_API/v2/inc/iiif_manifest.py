# Ouroboros config
import localConfig

# python modules
import json

# flask proper
from flask import render_template, request, session, redirect, make_response, Response, Blueprint, jsonify

# WSUDOR_API_app
from WSUDOR_API import cache
import WSUDOR_ContentTypes
from WSUDOR_Manager import fedora_handle
from WSUDOR_API import logging
logging = logging.getChild('iiif_manifest')

iiif_manifest_blueprint = Blueprint('iiif_manifest_v1', __name__)


# small function to skip caching, reads from localConfig.py
def skipCache():
	return localConfig.API_SKIP_CACHE


# IIIF_MANIFEST
#########################################################################################################

# object manifest
@iiif_manifest_blueprint.route("/%s/<identifier>" % (localConfig.IIIF_MANIFEST_PREFIX), methods=['POST', 'GET'])
def iiif_manifest(identifier):

	'''
	While using fedora 3.x, we'll be sending the PID as the identifier
	'''

	getParams = {each: request.values.getlist(each) for each in request.values}

	try:
		# fire retrieveManifest
		response = make_response( retrieveManifest(identifier) )
		response.headers['Access-Control-Allow-Origin'] = '*'
		response.headers['Access-Control-Allow-Methods'] = 'GET, POST'
		response.headers['Access-Control-Allow-Headers'] = 'x-prototype-version,x-requested-with'
		response.headers['Access-Control-Max-Age'] = 2520
		response.headers["Content-Type"] = "application/json"
		response.headers['X-Powered-By'] = 'ShoppingHorse'
		response.headers['Connection'] = 'Close'
		return response

	except Exception,e:
		logging.debug("iiif_manifest call unsuccessful.  Error: %s" % str(e))
		return jsonify({
				"status":"iiif_manifest call unsuccessful.",
				"message":str(e)
			}) 


# annotation list
@iiif_manifest_blueprint.route("/%s/list/<identifier>.json" % (localConfig.IIIF_MANIFEST_PREFIX), methods=['POST', 'GET'])
def iiif_annotation_list(identifier):

	getParams = {each:request.values.getlist(each) for each in request.values}

	try:
		# fire retrieveAnnotationList
		response = make_response( retrieveAnnotationList(identifier) )
		response.headers['Access-Control-Allow-Origin'] = '*'
		response.headers['Access-Control-Allow-Methods'] = 'GET, POST'
		response.headers['Access-Control-Allow-Headers'] = 'x-prototype-version,x-requested-with'
		response.headers['Access-Control-Max-Age'] = 2520
		response.headers["Content-Type"] = "application/json"
		response.headers['X-Powered-By'] = 'ShoppingHorse'
		response.headers['Connection'] = 'Close'
		return response

	except Exception,e:
		logging.debug("iiif_annotation_list call unsuccessful.  Error: %s" % str(e))
		return jsonify({
				"status":"iiif_manifest call unsuccessful.",
				"message":str(e)
			}) 


@cache.memoize(timeout=localConfig.API_CACHE_TIMEOUT, unless=skipCache)
def retrieveManifest(identifier):

	'''
	genIIIFManifest() is a function built-in to each content-type.
	In an effort to reduce how many times these manifests are generated, this function now tries
	to retreive from stored datastream first.  If not there, runs object method to generate,
	then tries again.
	'''

	# check for IIIF manifest datastream	
	ohandle = fedora_handle.get_object(identifier)
	if 'IIIF_MANIFEST' in ohandle.ds_list:
		logging.debug("manifest located and retrieved from Redis")
		return ohandle.getDatastreamObject('IIIF_MANIFEST').content
	else:
		logging.debug("generating manifest, storing as datastream, returning")
		obj = WSUDOR_ContentTypes.WSUDOR_Object(identifier)
		# fire content-type defined manifest generation
		return obj.genIIIFManifest()


@cache.memoize(timeout=localConfig.API_CACHE_TIMEOUT, unless=skipCache)
def retrieveAnnotationList(identifier):

	# check for IIIF manifest datastream
	ohandle = fedora_handle.get_object(identifier)
	if 'IIIF_ANNOLIST' in ohandle.ds_list:
		logging.debug("annotation list located and retrieved")
		return ohandle.getDatastreamObject('IIIF_ANNOLIST').content
	else:
		logging.debug("could not find annotation list for %s" % identifier)
		return jsonify({'status':'could not find annotation list for %s' % identifier})
