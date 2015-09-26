# Ouroboros config
import localConfig

# python modules
import json

# flask proper
from flask import render_template, request, session, redirect, make_response, Response

# WSUDOR_API_app
from WSUDOR_API import WSUDOR_API_app

# manifest-factory
from manifest_factory import factory as iiif_manifest_factory


# SETUP
#########################################################################################################
fac = iiif_manifest_factory.ManifestFactory()
# Where the resources live on the web
fac.set_base_metadata_uri("http:/digital.library.wayne.edu/iiif_manifest")
# Where the resources live on disk
fac.set_base_metadata_dir("/tmp/iiif_manifest")

# Default Image API information
fac.set_base_image_uri("http://digital.library.wayne.edu/loris")
fac.set_iiif_image_info(2.0, 2) # Version, ComplianceLevel

# 'warn' will print warnings, default level
# 'error' will turn off warnings
# 'error_on_warning' will make warnings into errors
fac.set_debug("warn")


# IIIF_MANIFEST MAIN
#########################################################################################################
@WSUDOR_API_app.route("/iiif_manifest/<identifier>", methods=['POST', 'GET'])
def iiif_manifest(identifier):		

	getParams = {each:request.values.getlist(each) for each in request.values}	

	try:
		# fire genManifest
		response = make_response( genManifest(identifier) )
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
		return '{{"WSUDOR_APIstatus":"WSUDOR_API iiif_manifest call unsuccessful.","WSUDOR_APIstatus iiif_manifest message":{exceptionErrorString}}}'.format(exceptionErrorString=json.dumps(str(e)))
	


def genManifest(identifier):

	'''
	Right here, you'll need to procure some information about the object from WSUDOR_Object handle
	'''

	# create root mani obj
	manifest = fac.manifest(label="Example Manifest")

	return json.dumps({'horse':'trap'})