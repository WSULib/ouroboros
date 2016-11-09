# -*- coding: utf-8 -*-
# WSUDOR_API : errors


# Ouroboros config
import localConfig

# flask proper
from flask import jsonify, make_response

# WSUDOR_API_app
from WSUDOR_API import WSUDOR_API_app


'''
desc: provides custom error responses with messages and HTTP codes
'''


# 401
@WSUDOR_API_app.errorhandler(401)
def e401(error):
    return make_response(jsonify({
    	'http_status_code': '401',
    	'msg': error.description
	}), 401)


# 403
@WSUDOR_API_app.errorhandler(403)
def e403(error):
    return make_response(jsonify({
    	'http_status_code': '403',
    	'msg': error.description
	}), 403)


# 404
@WSUDOR_API_app.errorhandler(404)
def e404(error):
    return make_response(jsonify({
    	'http_status_code': '404',
    	'msg': error.description
	}), 404)


# 500
@WSUDOR_API_app.errorhandler(500)
def e500(error):
    return make_response(jsonify({
    	'http_status_code': '500',
    	'msg': error.description
	}), 500)

