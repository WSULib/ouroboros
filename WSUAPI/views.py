# Ouroboros config
import localConfig

# python modules
import json

# flask proper
from flask import render_template, request, session, redirect, make_response, Response

# WSUAPI_app
from WSUAPI import WSUAPI_app
from WSUAPImain import WSUAPImain


# session data secret key
####################################
WSUAPI_app.secret_key = 'WSUDOR-WSUAPI'
####################################


# GENERAL
#########################################################################################################
@WSUAPI_app.route("/{WSUAPI_PREFIX}/".format(WSUAPI_PREFIX=localConfig.WSUAPI_PREFIX), methods=['POST', 'GET'])
@WSUAPI_app.route("/{WSUAPI_PREFIX}".format(WSUAPI_PREFIX=localConfig.WSUAPI_PREFIX), methods=['POST', 'GET'])
def index():		

	print "HTTP METHOD:",request.method
	
	'''
	Twisted must have this parameter parsing built-in.
	For feeding WSUAPImain in Flask app form, we perform here.
	'''	
	getParams = {each:request.values.getlist(each) for each in request.values}	

	try:
		response = make_response(WSUAPImain(getParams))
		response.headers['Access-Control-Allow-Origin'] = '*'
		response.headers['Access-Control-Allow-Methods'] = 'GET, POST'
		response.headers['Access-Control-Allow-Headers'] = 'x-prototype-version,x-requested-with'
		response.headers['Access-Control-Max-Age'] = 2520
		response.headers["Content-Type"] = "application/json"		
		response.headers['X-Powered-By'] = 'ShoppingHorse'
		response.headers['Connection'] = 'Close'
		return response

	except Exception,e:
		print "WSUAPI call unsuccessful.  Error:",str(e)
		return '{{"WSUAPIstatus":"WSUAPI call unsuccessful.","WSUAPIstatus message":{exceptionErrorString}}}'.format(exceptionErrorString=json.dumps(str(e)))
	

