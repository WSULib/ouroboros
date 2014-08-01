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
@WSUAPI_app.route("/{WSUAPI_prefix}/".format(WSUAPI_prefix=localConfig.WSUAPI_prefix), methods=['POST', 'GET'])
@WSUAPI_app.route("/{WSUAPI_prefix}".format(WSUAPI_prefix=localConfig.WSUAPI_prefix), methods=['POST', 'GET'])
def index():		
	
	'''
	Twisted must have this parameter parsing built-in.
	For feeding WSUAPImain in Flask app form, performed here.
	'''
	
	getParams = {each:request.values.getlist(each) for each in request.args}	

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
		return '{{"WSUAPIstatus":{exceptionErrorString}}}'.format(exceptionErrorString=json.dumps(str(e)))
	

