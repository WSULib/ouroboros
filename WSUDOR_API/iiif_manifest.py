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
	fac = iiif_manifest_factory.ManifestFactory()
	return json.dumps({"id":identifier})