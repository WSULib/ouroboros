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
from functions.packagedFunctions import singleObjectPackage
from functions.fedDataSpy import makeSymLink

# manifest-factory
from manifest_factory import factory as iiif_manifest_factory



# SETUP
#########################################################################################################
iiif_manifest_factory_instance = iiif_manifest_factory.ManifestFactory()
# Where the resources live on the web
iiif_manifest_factory_instance.set_base_metadata_uri("http:/digital.library.wayne.edu/iiif_manifest")
# Where the resources live on disk
iiif_manifest_factory_instance.set_base_metadata_dir("/tmp/iiif_manifest")

# Default Image API information
iiif_manifest_factory_instance.set_base_image_uri("http://digital.library.wayne.edu/loris")
iiif_manifest_factory_instance.set_iiif_image_info(2.0, 2) # Version, ComplianceLevel

# 'warn' will print warnings, default level
# 'error' will turn off warnings
# 'error_on_warning' will make warnings into errors
iiif_manifest_factory_instance.set_debug("warn")


# small function to skip caching, reads from localConfig.py
def skipCache():
	return localConfig.API_SKIP_CACHE


# IIIF_MANIFEST MAIN
#########################################################################################################
@WSUDOR_API_app.route("/{IIIF_MANIFEST_PREFIX}/<identifier>".format(IIIF_MANIFEST_PREFIX=localConfig.IIIF_MANIFEST_PREFIX), methods=['POST', 'GET'])
def iiif_manifest(identifier):		

	'''
	While using fedora 3.x, we'll be sending the PID as the identifier
	'''

	getParams = {each:request.values.getlist(each) for each in request.values}

	# try:
	# fire genManifest
	response = make_response( genManifest(identifier,getParams) )
	response.headers['Access-Control-Allow-Origin'] = '*'
	response.headers['Access-Control-Allow-Methods'] = 'GET, POST'
	response.headers['Access-Control-Allow-Headers'] = 'x-prototype-version,x-requested-with'
	response.headers['Access-Control-Max-Age'] = 2520
	response.headers["Content-Type"] = "application/json"		
	response.headers['X-Powered-By'] = 'ShoppingHorse'
	response.headers['Connection'] = 'Close'
	return response

	# except Exception,e:
	# 	print "WSUDOR_API iiif_manifest call unsuccessful.  Error:",str(e)
	# 	return '{{"WSUDOR_APIstatus":"WSUDOR_API iiif_manifest call unsuccessful.","WSUDOR_APIstatus iiif_manifest message":{exceptionErrorString}}}'.format(exceptionErrorString=json.dumps(str(e)))
		

@cache.memoize(timeout=localConfig.API_CACHE_TIMEOUT, unless=skipCache)
def genManifest(identifier,getParams):

	'''
	genIIIFManifest() is a function built-in to each content-type.
	This function is run here, letting the content model generate the proper manifest JSON string to return
	'''

	# open object_handle
	obj_handle = WSUDOR_ContentTypes.WSUDOR_Object(identifier)

	# fire content-type defined manifest generation
	return obj_handle.genIIIFManifest(iiif_manifest_factory_instance, identifier, getParams)
	








