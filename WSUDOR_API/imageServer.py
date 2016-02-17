# Ouroboros config
import localConfig

# flask proper
from flask import request, redirect, Response

# WSUDOR_API_app
from WSUDOR_API import cache
from WSUDOR_API import WSUDOR_API_app


# small function to skip caching, reads from localConfig.py
def skipCache():
	return localConfig.API_SKIP_CACHE


# IIIF_MANIFEST MAIN
#########################################################################################################
@WSUDOR_API_app.route("/imageServer", methods=['POST', 'GET'])
def imageServer():		

	'''
	This small route directs traffic from old image server @ /imageServer, 
	to new Loris server @ /loris
	'''

	# pull out PID and datastream ID
	obj = request.args.get('obj', '')
	ds = request.args.get('ds', '')

	# return redirect
	print "redirecting imageServer request:",obj,ds
	return redirect("http://%s/loris/fedora:%s|%s/full/full/0/default.jpg" % (localConfig.PUBLIC_HOST, obj, ds), code=301)

	








