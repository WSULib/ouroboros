# WSU Digital Collections Infrastructure API (WSUDOR_API)
# Designed to query and combine results from multiple back-end systems into a single JSON package.

# IMPORTS
# python proper
import os
import sys
import json
import argparse
import ast
import re
import traceback

import localConfig

# WSUDOR_API modules
from WSUDOR_API import cache
from functions.utils import *
from functions.availableFunctions import *
from functions.packagedFunctions import *

# CACHE
#########################################################################################################
# small function to skip caching, reads from localConfig.py
def skipCache():
	return localConfig.API_SKIP_CACHE


'''
Consider using 'make_cache_key'
'''
@cache.memoize(timeout=localConfig.API_CACHE_TIMEOUT, unless=skipCache)
def WSUDOR_API_main(getParams):

	# ITERATE THROUGH FUNCTION LIST 	
	def runFunctions():	
		
		# get functions get parameters		
		funcs = getParams['functions[]']		

		for func in funcs:		
			if func in globals():
				funcName = globals()[func]				
				print "running",func			
				try:
					JSONdict[funcName.__name__] = funcName(getParams) #passes *all* GET params from mainRouter()
				except Exception,e:
					traceback.print_exc(file=sys.stdout)
					JSONdict[funcName.__name__] = '{{"status":{exceptionErrorString}}}'.format(exceptionErrorString=json.dumps(str(e)))
			else:
				print "Function not found"


	# JSON RETURN	
	# function to zip and return all JSON fragments to fedClerk
	def JSONreturn():	

		JSONevaluated = {}
		for each in JSONdict:					
			JSONevaluated[each] = json.loads(JSONdict[each])
		JSONpackage = json.dumps(JSONevaluated)

		# return JSON package
		return JSONpackage	
	

	# EXECUTE	
	JSONdict = {}	

	# build API params
	APIParams = {}
	for param in getParams:
		APIParams[param] = getParams[param]

	# remove password whenever present	
	APIParams.pop("password", None)

	# strip passwords from APIParams	
	APIParamsJSON = json.dumps(APIParams)
	JSONdict['APIParams'] = APIParamsJSON

	# if functions declared
	if 'functions[]' in getParams:
		#runs functions in functions[]		
		runFunctions()	# this builds up JSONdict, fragments from each function
		return JSONreturn() # this returns that dictionary and outputs as JSON
	# NO functions declared
	else:
		return '{"WSUDOR_API_status": "No functions declared."}'
	




