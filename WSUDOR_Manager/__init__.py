# root file, app instantiator
import os
import sys

# modules / packages import
from flask import Flask, render_template, g
from flask.ext.sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine, MetaData
from flask.ext.login import LoginManager
import localConfig
from localConfig import *
from eulfedora.server import Repository
from celery import Celery
import xmlrpclib


##########################################################################################
# create app
##########################################################################################
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


##########################################################################################
# instantiate fedora_handle
##########################################################################################
'''
Needs Improvement.

If no args passed, assume 'python runserver.py', and thus, not celery worker.
	- fire generic fedora_handle with username / password from localConfig
	- handles API-M calls and some tasks (e.g. solrIndexer)
	- but again, would be ideal if these all worked from generic, localhost fedora_handle

If celery worker -- with multiple args -- fire fedora_handle based on username
	- set fedora_handle to False, knowing it will get built in fedora_handle
'''
print sys.argv
if len(sys.argv) == 1:
	print "generating generic fedora_handle and generic celery worker"	
	fedora_handle = Repository(FEDORA_ROOT, localConfig.FEDORA_USER, localConfig.FEDORA_PASSWORD, 'wayne')
	fire_cw = True	
else:
	print "generating user authenticated fedora_handle"
	app.config['USERNAME'] = sys.argv[5]
	print "app.config username is", app.config['USERNAME']
	fedora_handle = False
	fire_cw = False


##########################################################################################
# instantiate celery
##########################################################################################

# class for User Celery Workers
class CeleryWorker(object):

    sup_server = xmlrpclib.Server('http://127.0.0.1:9001')
    
    def __init__(self,username,password):
        self.username = username
        self.password = password       


    def _writeConfFile(self):
        print "adding celery conf file"
        # fire the suprevisor celery worker process
        celery_process = '''[program:celery-%(username)s]
command=/usr/local/lib/venvs/ouroboros/bin/celery worker -A WSUDOR_Manager.celery -Q %(username)s --loglevel=Info --concurrency=4 -n %(username)s.local --without-mingle
directory=/opt/ouroboros
user = ouroboros
autostart=true
autorestart=true
stderr_logfile=/var/log/celery-%(username)s.err.log
stdout_logfile=/var/log/celery-%(username)s.out.log''' % {'username': self.username}

        filename = '/etc/supervisor/conf.d/celery-%s.conf' % self.username
        if not os.path.exists(filename):
            with open(filename ,'w') as fhand:
                fhand.write(celery_process)
            return filename
        else:
            print "Conf files exists, skipping"
            return False


    def _removeConfFile(self):
        print "remove celery conf file"
        filename = '/etc/supervisor/conf.d/celery-%s.conf' % self.username
        if os.path.exists(filename):
            return os.remove(filename)
        else:
            print "could not find conf file, skipping"
            return False


    def _startSupervisorProcess(self):
        print "adding celery proccessGroup from supervisor"
        try:
            self.sup_server.supervisor.reloadConfig()
            self.sup_server.supervisor.addProcessGroup('celery-%s' % self.username)
        except:
            return False


    def _restartSupervisorProcess(self):
        try:
            self.sup_server.supervisor.stopProcess('celery-%s' % self.username)
        except:
            print "could not stop process"
        try:
            self.sup_server.supervisor.startProcess('celery-%s' % self.username)
        except:
            print "could not start process"


    def _stopSupervisorProcess(self):
        print "removing celery proccessGroup from supervisor"           
        try:
            process_group = 'celery-%s' % self.username
            self.sup_server.supervisor.stopProcess(process_group)
            self.sup_server.supervisor.removeProcessGroup(process_group)
        except:
            return False


    def start(self):
        self._writeConfFile()
        self._startSupervisorProcess()


    def restart(self):
        self._restartSupervisorProcess()


    def stop(self):        
        self._removeConfFile()
        self._stopSupervisorProcess()


app.config.update(
	CELERY_BROKER_URL='redis://localhost:6379/%s' % (localConfig.REDIS_BROKER_DB),
	RESULT_SERIALIZER='json',
)

def make_celery(app):
	celery = Celery(backend='redis://localhost:6379/1')
	celery.config_from_object('cl.celeryConfig')
	TaskBase = celery.Task
	class ContextTask(TaskBase):
		abstract = True
		def __call__(self, *args, **kwargs):
			with app.app_context():
				return TaskBase.__call__(self, *args, **kwargs)
	celery.Task = ContextTask
	return celery

celery = make_celery(app)

# assuming Ouroboros Celery worker
if fire_cw:
	# fire celery worker
	print "firing generic celery worker"
	cw = CeleryWorker("celery",False)
	cw.start()


##########################################################################################
# setup db
##########################################################################################
db = SQLAlchemy(app)
engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'], convert_unicode=True)
metadata = MetaData(bind=engine)
db_con = engine.connect()

# start up login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


##########################################################################################
# finish up
##########################################################################################
# import WSUDOR ContentTypes
import WSUDOR_ContentTypes
from WSUDOR_ContentTypes import *

# get handlers
import views

# ouroboros_assets
import ouroboros_assets

# generate required folders if not present
if not os.path.exists('/tmp/Ouroboros'):
	os.mkdir('/tmp/Ouroboros')
if not os.path.exists('/tmp/Ouroboros/ingest_workspace'):
	os.mkdir('/tmp/Ouroboros/ingest_workspace')
if not os.path.exists('/home/ouroboros/ingest_jobs'):
	os.mkdir('/home/ouroboros/ingest_jobs')






