# -*- coding: utf-8 -*-
# WSUDOR_API : views.py

######################################################################
## HOMEGROWN
######################################################################
# # Ouroboros config
# import localConfig

# # flask proper
# from flask import abort, jsonify, make_response, redirect, render_template, request, Response, session 

# # WSUDOR_API_app
# from WSUDOR_API import WSUDOR_API_app, errors
# from WSUDOR_Manager.helpers import gzipped, timing




# # DIAGNOSTIC
# @WSUDOR_API_app.route("/%s/error_check/<status_code>" % (localConfig.WSUDOR_API_PREFIX), methods=['GET'])
# @gzipped
# def error_check(status_code):

# 	'''
# 	desc: accpets HTTP status code and checks API response
# 	'''

# 	try:
# 		status_code_int = int(status_code)
# 		msg = 'error check successful for %d' % (status_code_int)
# 	except:
# 		status_code_int = 500
# 		msg = 'could not parse error code to check, try something like 401, 403, 404, 500, etc.'

# 	abort(status_code_int, msg)


######################################################################
## Flask-RESTful
######################################################################
# Ouroboros config
import localConfig

# WSUDOR_API_app
from WSUDOR_API import WSUDOR_API_app, api, models


# routing
api.add_resource(models.HelloWorld, '/%s' % (localConfig.WSUDOR_API_PREFIX), endpoint='helloworld')


















