# IMPORTS
####################################################################################################
import os
import sys
import json
import argparse
import ast
import re
import importlib


'''
All project python files should match their URL.  For example, "coneyDogMaker.py" would be triggered with "/WSUAPI/projects/coneyDogMaker"
The project python file itself should initialize with a main() function.
	def main():
		return PROJECT_RESULTS
	if __name__ == "__main__":
	        main()

Each project should return a two-part dictionary
response['headers'] = headers for Twisted server to lace results in
response['content'] = actual results

** Consider localizing working directory for each project, then drop back to /var/opt/fedClerk afterwards

'''

def ProjectsMain(getParams,requestPath):

	# get project
	print "requestPath is as such:",requestPath
	project = requestPath.split("/")[-1]
	print "Project is:",project

	# run function
	project = importlib.import_module("lib.Projects."+project+"."+project)
	results = project.main(getParams,requestPath)
	return results

def defaultFunc(getParams,requestPath):
	response = {}
	response['headers'] = {}
	response['headers']['Access-Control-Allow-Origin'] = '*'
	response['headers']['Access-Control-Allow-Methods'] = 'GET, POST'
	response['headers']['Access-Control-Allow-Headers'] = 'x-prototype-version,x-requested-with'
	response['headers']['Access-Control-Max-Age'] = 2520
	response['headers']["content-type"] = "application/json"
	response['headers']['Connection'] = 'Close'
	response['headers']['X-Powered-By'] = 'ProjectsHorse'
	response['content'] = '{"Projects API": "Path did not return any projects."}'
	return response
