# utilities
import datetime
import hashlib
import requests
from requests.auth import HTTPBasicAuth
from flask import render_template, session
import json
import pickle
from functools import wraps
import mimetypes
import xmlrpclib


from localConfig import *
from WSUDOR_Manager import models, app, fedoraHandles, celery
from eulfedora.server import Repository

def login(username,password):

		print "\n\n\nFIRING LOGIN\n\n\n"

		try:
			# fire celery worker
			# fire the suprevisor celery worker process
			celery_process = '''[program:celery-%(username)s]
	command=/usr/local/lib/venvs/ouroboros/bin/celery worker -A cl.cl -Q %(username)s --loglevel=Info --concurrency=1
	directory=/opt/ouroboros
	user = ouroboros
	autostart=true
	autorestart=true
	stderr_logfile=/var/log/celery-%(username)s.err.log
	stdout_logfile=/var/log/celery-%(username)s.out.log''' % {'username': username}

			with open('/etc/supervisor/conf.d/celery-%s.conf' % username,'w') as fhand:
				fhand.write(celery_process)
			server = xmlrpclib.Server('http://127.0.0.1:9001')
			server.supervisor.reloadConfig()
			server.supervisor.addProcessGroup('celery-%s' % username)

			# add queue
			celery.control.add_consumer(username,reply=True)
		
		except:
			print "COULD NOT START CELERY WORKER"


escapeRules = {'+': r'\+',
			 '-': r'\-',
			 '&': r'%26',
			 '|': r'\|',
			 '!': r'\!',
			 '(': r'\(',
			 ')': r'\)',
			 '{': r'\{',
			 '}': r'\}',
			 '[': r'\[',
			 ']': r'\]',
			 '^': r'\^',
			 '~': r'\~',             
			 '?': r'\?',
			 ':': r'\:',             
			 ';': r'\;',             
			 ' ': r'+'
			 }

def escapedSeq(term):
		""" Yield the next string based on the
				next character (either this char
				or escaped version """
		for char in term:
				if char in escapeRules.keys():
						yield escapeRules[char]
				else:
						yield char

def escapeSolrArg(term):
		""" Apply escaping to the passed in query terms
				escaping special characters like : , etc"""
		term = term.replace('\\', r'\\')   # escape \ first
		return "".join([nextStr for nextStr in escapedSeq(term)])



def returnOAISets(context):
		# returns list of tuples, in format (collection PID, OAI set name, OAI set ID)
		query_statement = "select $subject $setSpec $setName from <#ri> where { $subject <http://www.openarchives.org/OAI/2.0/setSpec> $setSpec . $subject <http://www.openarchives.org/OAI/2.0/setName> $setName . }"
		base_URL = "http://%s:%s@localhost/fedora/risearch" % (FEDORA_USER,FEDORA_PASSWORD)
		payload = {
				"lang" : "sparql",
				"query" : query_statement,
				"flush" : "false",
				"type" : "tuples",
				"format" : "JSON"
		}
		r = requests.post(base_URL, auth=HTTPBasicAuth(FEDORA_USER, FEDORA_PASSWORD), data=payload )
		risearch = json.loads(r.text)

		if context == "dropdown":
				shared_relationships = [ (each['subject'], each['setName']) for each in risearch['results'] ]   
		else:
				shared_relationships = [ (each['subject'], each['setName'], each['setSpec']) for each in risearch['results'] ]  

		return shared_relationships


def applicationError(error_msg):
		return render_template("applicationError.html",error_msg=error_msg)


# human readable file size
def sizeof_fmt(num, suffix='B'):
		for unit in ['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']:
				if abs(num) < 1024.0:
						return "%3.1f%s%s" % (num, unit, suffix)
				num /= 1024.0
		return "%.1f%s%s" % (num, 'Yi', suffix)



# DECORATORS
#########################################################################################################
# decorated function will redirect if no objects currently selected 
def objects_needed(f):
		@wraps(f)
		def decorated_function(*args, **kwargs):        

				try:
						username = session['username']
				except:
						return render_template("noObjs.html")

				userSelectedPIDs = models.user_pids.query.filter_by(username=username,status=True)  

				if userSelectedPIDs.count() == 0 and 'job_type' in kwargs and kwargs['job_type'] == 'obj_loop':         
						return render_template("noObjs.html")       
				return f(*args, **kwargs)       
		return decorated_function


# pass APP_PREFIX to all templates
@app.context_processor
def inject_prefix():
		return {
				'APP_PREFIX':APP_PREFIX,
				'APP_HOST':APP_HOST
		}


# OPINIONATED MIMETYPES
#########################################################################################################
# WSUDOR opinionated mimes
opinionated_mimes = {
		# images
		"image/jp2":".jp2",
		"image/jpeg":".jpg",
		"audio/wav":".wav"
}   

# push to mimetypes.types_map
for k, v in opinionated_mimes.items():
		# reversed here
		mimetypes.types_map[v] = k













