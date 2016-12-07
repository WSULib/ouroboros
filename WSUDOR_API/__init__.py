# root file, app instantiator

import localConfig

# modules / packages import
from flask import Flask, render_template, g
from flask.ext.login import LoginManager
from flask.ext.cache import Cache
from flask_restful import Api

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
		print prefix

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

'''
The PrefixMiddleware class below works very nicely for adding a prefix to an app.
However, choosing to have each API version, wrapped in its `v#` folder,
generate it's own prefix.  See `__init__.py` for each `v#` folder.
'''
# class PrefixMiddleware(object):

#     def __init__(self, app, prefix=''):
#         self.app = app
#         self.prefix = prefix

#     def __call__(self, environ, start_response):

#         if environ['PATH_INFO'].startswith(self.prefix):
#             environ['PATH_INFO'] = environ['PATH_INFO'][len(self.prefix):]
#             environ['SCRIPT_NAME'] = self.prefix
#             return self.app(environ, start_response)
#         else:
#             start_response('404', [('Content-Type', 'text/plain')])
#             return ["This url does not belong to the app.".encode()]
# '''
# Requires leading slash in prefix below
# '''
# if not localConfig.WSUDOR_API_PREFIX.startswith('/'):
# 	app_prefix = '/%s' % localConfig.WSUDOR_API_PREFIX
# else:
# 	app_prefix = localConfig.WSUDOR_API_PREFIX
# WSUDOR_API_app.wsgi_app = PrefixMiddleware(WSUDOR_API_app.wsgi_app, prefix=app_prefix)

# Flask-Cache for API
cache = Cache(WSUDOR_API_app, config={'CACHE_TYPE': 'simple'})

########################################################
# v1
########################################################
from v1 import views, bitStream, lorisProxy




########################################################
# v2
########################################################
# Flask-RESTful init for primary, metadata API
# api = Api(WSUDOR_API_app, prefix='/v2')
api = Api(WSUDOR_API_app)
from v2 import views
# load auxillary API handlers
from v2.inc import bitStream, lorisProxy





