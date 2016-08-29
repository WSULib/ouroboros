# WSU Digital Collections Infrastructure API (WSUDOR_API)
# Designed to query and combine results from multiple back-end systems into a single JSON package.

# IMPORTS
# python proper
import sys
import json
import traceback
import localConfig

# WSUDOR_API modules
from WSUDOR_API import cache
from WSUDOR_API.bitStream import BitStream
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
		
		# run debug mode
		if 'debug' in getParams and getParams['debug'][0] == 'true':
			# get functions get parameters		
			funcs = getParams['functions[]']		

			for func in funcs:		
				if func in globals():
					funcName = globals()[func]				
					print "running",func			
					JSONdict[funcName.__name__] = funcName(getParams) #passes *all* GET params from mainRouter()
				else:
					print "Function not found"

		elif 'debug' in getParams and getParams['debug'][0] != 'true':
			JSONdict['debug'] = json.dumps(str("unrecognized value"))

		# normal mode
		else:
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
						JSONdict[funcName.__name__] = '{{"status":%s}}' % (json.dumps(str(e)))
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

	# determine if user logged in
	if 'active_user' in getParams:
		
		# check authentication with cookieAuth()
		print "checking user auth..."
		JSONdict['user_auth'] = cookieAuth(getParams)

		# if user is logged in and part of staff group, return bitStream download tokens
		user_auth = json.loads(JSONdict['user_auth'])
		if user_auth['hashMatch'] and getParams['username'][0] in localConfig.BITSTREAM_CLEARED_USERNAMES:

			print "generating bitStream token dictionary"
			JSONdict['bitStream'] = json.dumps(BitStream.genAllTokens(getParams['PID'][0], localConfig.BITSTREAM_KEY))

	# if functions declared
	if 'functions[]' in getParams:
		#runs functions in functions[]		
		runFunctions()	# this builds up JSONdict, fragments from each function
		return JSONreturn() # this returns that dictionary and outputs as JSON
	# NO functions declared
	else:
		return '{"WSUDOR_API_status": "No functions declared."}'
	




