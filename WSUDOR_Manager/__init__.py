# root file, app instantiator
import os

# modules / packages import
from flask import Flask, render_template, g
from flask.ext.sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine, MetaData
from flask.ext.login import LoginManager
import localConfig


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
app = Flask(__name__)

# if using app prefix, wrap Flask app in ReverseProxied class from above
if localConfig.APP_PREFIX_USE:
	print "wrapping WSUDOR_Manager for reverse proxy"
	app.wsgi_app = ReverseProxied(app.wsgi_app)
	app.config["APPLICATION_ROOT"] = "/%s" % localConfig.APP_PREFIX

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://%s:%s@localhost/%s' % (localConfig.MYSQL_USERNAME, localConfig.MYSQL_PASSWORD, localConfig.MYSQL_DATABASE ) 

#setup db
db = SQLAlchemy(app)
engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'], convert_unicode=True)
metadata = MetaData(bind=engine)
db_con = engine.connect()

# start up login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# import WSUDOR ContentTypes
import WSUDOR_ContentTypes
from WSUDOR_ContentTypes import *

# get handlers
import views

# generate required folders if not present
if not os.path.exists('/tmp/Ouroboros'):
	os.mkdir('/tmp/Ouroboros')
if not os.path.exists('/tmp/Ouroboros/ingest_workspace'):
	os.mkdir('/tmp/Ouroboros/ingest_workspace')
if not os.path.exists('/tmp/Ouroboros/ingest_jobs'):
	os.mkdir('/tmp/Ouroboros/ingest_jobs')






