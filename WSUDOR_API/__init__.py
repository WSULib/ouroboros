# root file, app instantiator

import urllib

import localConfig
from localConfig import logging, LOGGING_STREAM, LOGGING_LEVEL

# setup logging for WSUDOR_API
logging.basicConfig(stream=LOGGING_STREAM, level=LOGGING_LEVEL)

# modules / packages import
from flask import Flask, render_template, g, redirect, jsonify, request
from flask.ext.login import LoginManager
from flask.ext.cache import Cache

from werkzeug.routing import BaseConverter




# http://flask.pocoo.org/snippets/35/
class ReverseProxied(object):
	'''Wrap the application in this middleware and configure the 
	front-end server to add these headers, to let you quietly bind 
	this to a URL other than / and to an HTTP scheme that is 
	different than what is used locally.
	In nginx:
	location /myprefix {
		proxy_pass http://192.168.0.1:5001;
		proxy_set_header Host $host;
		proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
		proxy_set_header X-Scheme $scheme;
		proxy_set_header X-Script-Name /myprefix;
		}
	:param app: the WSGI application
	'''
	def __init__(self, app, prefix=''):
		self.app = app
		self.prefix = prefix		
		logging.debug("%s" % prefix)

	def __call__(self, environ, start_response):
		script_name = environ.get('HTTP_X_SCRIPT_NAME', '')
		if script_name:
			environ['SCRIPT_NAME'] = script_name
			path_info = environ['PATH_INFO']
			if path_info.startswith(script_name):
				environ['PATH_INFO'] = path_info[len(script_name):]

		scheme = environ.get('HTTP_X_SCHEME', '')
		if scheme:
			environ['wsgi.url_scheme'] = scheme
		return self.app(environ, start_response)

# create app
WSUDOR_API_app = Flask(__name__)
WSUDOR_API_app.wsgi_app = ReverseProxied(WSUDOR_API_app.wsgi_app)
WSUDOR_API_app.debug = True
WSUDOR_API_app.secret_key = 'WSUDOR_API'

# Flask-Cache for API
cache = Cache(WSUDOR_API_app, config={'CACHE_TYPE': 'simple'})

# capture default API calls and redirect
class RegexConverter(BaseConverter):
	def __init__(self, url_map, *items):
		super(RegexConverter, self).__init__(url_map)
		self.regex = items[0]
WSUDOR_API_app.url_map.converters['regex'] = RegexConverter

@WSUDOR_API_app.route('/%s/v<regex("[0-9]"):version_number><regex(".*"):url_suffix>' % localConfig.WSUDOR_API_PREFIX, methods=['GET', 'POST'])
def example(version_number,url_suffix):

	# build url
	protocol = request.url.split(":")[0]
	default_api_target = '%s://%s/%s%s' % (protocol, localConfig.APP_HOST, localConfig.WSUDOR_API_PREFIX, url_suffix)

	if request.method == 'GET':
		# target url		
		default_api_target += "?%s" % urllib.urlencode(request.args.items())
		return redirect(default_api_target, code=307)

	if request.method == 'POST':

		# return message to user to use default /api route
		return jsonify({
			'msg':'It looks as though you are sending a POST request to the current, default API version: %s.  Try /api instead of /api/v%s.  The base URL for this request, and a possible GET alternative are provided.' % (version_number,version_number),
			'api_version_request':version_number,
			'request_method':request.method,
			'api_url_base':default_api_target,
			'GET_alternative':'%s?%s' % (default_api_target, urllib.urlencode(request.form.to_dict()).replace('%253A',':'))
		})

# import api versions
import v1, v2









