# WSU Digital Collections Infrastructure API (WSUAPI)
# Designed to query and combine results from multiple back-end systems into a single JSON package.

# IMPORTS
####################################################################################################
# python proper
import os
import sys
import json
import argparse
import ast
import re

# WSUAPI modules
from functions.utils import *
from functions.availableFunctions import *
from functions.availableFunctions_v2 import *

def WSUAPImain(getParams):

	# ITERATE THROUGH FUNCTION LIST 
	####################################################################################################
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
					JSONdict[funcName.__name__] = '{{"status":{exceptionErrorString}}}'.format(exceptionErrorString=json.dumps(str(e)))
			else:
				print "Function not found"

	# JSON RETURN
	####################################################################################################
	# function to zip and return all JSON fragments to fedClerk
	def JSONreturn():			
		JSONevaluated = {}
		for each in JSONdict:					
			JSONevaluated[each] = json.loads(JSONdict[each])
		JSONpackage = json.dumps(JSONevaluated)

		# return JSON package
		return JSONpackage	
	

	# EXECUTE
	####################################################################################################
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
		return '{"WSUAPI_status": "No functions declared."}'	


if __name__ == '__main__':	
	WSUAPImain()
	




