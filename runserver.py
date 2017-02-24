# library
from twisted.web.wsgi import WSGIResource
from twisted.web.server import Site
from twisted.internet import reactor, defer
from twisted.internet.task import deferLater
from twisted.web.server import NOT_DONE_YET
from twisted.web import server, resource
from twisted.python import log
from stompest.async import Stomp
from stompest.async.listener import SubscriptionListener
from stompest.config import StompConfig
from stompest.protocol import StompSpec
import json
import logging
import subprocess
# from subprocess import check_output, CalledProcessError

# for Ouroboros pid management
import os
import atexit
import lockfile
import xmlrpclib
import time

# local
from localConfig import *

# import WSUDOR_Manager app
from WSUDOR_Manager import app as WSUDOR_Manager_app

# import WSUDOR_API app
from WSUDOR_API import WSUDOR_API_app

# import main indexer
from WSUDOR_Indexer import WSUDOR_Indexer


# Ouroboros pidfile ##############################################################
# function to create/remove Ouroboros pidfile
def pidfileCreate():
	print "creating pidfile"

	pidfile = "/var/run/ouroboros/%s.pid" % (APP_NAME)

	if os.path.exists("/var/run/ouroboros/%s.pid" % (APP_NAME)):
		print "pidlock found, investigating..."
		
		# get instances of "runserver.py"
		try:
			output = subprocess.check_output(('lsof', '-i', ':%s' % WSUDOR_MANAGER_PORT))
			print "something is already running on %s" % WSUDOR_MANAGER_PORT
			raise Exception("aborting")
		except subprocess.CalledProcessError:
			print "could not find other running instances of ouroboros, removing pidlock and continuing..."
			os.system("rm /var/run/ouroboros/*")
			time.sleep(2)			

	with open(pidfile,"w") as fhand:
		fhand.write(str(os.getpid()))
	ouroboros_pidlock = lockfile.LockFile("/var/run/ouroboros/%s.pid" % (APP_NAME))
	ouroboros_pidlock.acquire()
	return ouroboros_pidlock

def pidfileRemove():
	print "Removing pidfile"
	ouroboros_pidlock.release()
	os.system("rm /var/run/ouroboros/%s.pid" % (APP_NAME))


# Ouroboros shutdown ##############################################################
def shutdown():
	print "received kill command, attempting to shutdown gracefully..."

	# remove PID
	pidfileRemove()

	# remove generic celery task ONLY
	print "removing generic celery tasks from supervisor"
	celery_conf_files = os.listdir('/etc/supervisor/conf.d')
	for conf in celery_conf_files:
		if conf == "celery-celery.conf":
			process_group = conf.split(".conf")[0]
			print "stopping celery worker: %s" % process_group
			sup_server = xmlrpclib.Server('http://127.0.0.1:9001')
			sup_server.supervisor.stopProcessGroup(process_group)
			sup_server.supervisor.removeProcessGroup(process_group)
			os.system('rm /etc/supervisor/conf.d/%s' % conf)

	print "<-- Ouroboros says thanks for playing -->"


# Fedora Commons Messaging STOMP protocol consumer ##############################################################
'''
Prod: Connected to JSM Messaging service on stomp://localhost:FEDCONSUMER_PORT (usually 61616),
routes 'fedEvents' to fedoraConsumer()
'''
class IndexerWorker(object):

	QUEUE = "/topic/fedora.apim.update"
	ERROR_QUEUE = '/queue/testConsumerError'


	def __init__(self, config=None):
		if config is None:
			config = StompConfig('tcp://localhost:%s' % (FEDCONSUMER_PORT))
		self.config = config

	@defer.inlineCallbacks
	def run(self):
		client = Stomp(self.config)
		yield client.connect()
		headers = {
			# client-individual mode is necessary for concurrent processing
			StompSpec.ACK_HEADER: StompSpec.ACK_CLIENT_INDIVIDUAL,
			# the maximal number of messages the broker will let you work on at the same time
			'activemq.prefetchSize': '100',
		}
		client.subscribe(self.QUEUE, headers, listener=SubscriptionListener(self.consume))

	def consume(self, client, frame):
		indexer = WSUDOR_Indexer(frame)
		indexer.act()


# twisted liseners
logging.basicConfig(level=LOGGING_LEVEL)

# WSUDOR_Manager
WSUDOR_Manager_resource = WSGIResource(reactor, reactor.getThreadPool(), WSUDOR_Manager_app)
WSUDOR_Manager_site = Site(WSUDOR_Manager_resource)

# WSUDOR_API_app
WSUDOR_API_resource = WSGIResource(reactor, reactor.getThreadPool(), WSUDOR_API_app)
WSUDOR_API_site = Site(WSUDOR_API_resource)

if __name__ == '__main__':

	# write PID to /var/run
	ouroboros_pidlock = pidfileCreate()
	atexit.register(shutdown)

	# WSUDOR Manager
	if WSUDOR_MANAGER_FIRE == True:
		print "Starting WSUDOR_Manager..."
		reactor.listenTCP( WSUDOR_MANAGER_PORT, WSUDOR_Manager_site)

	# WSUDOR_API
	if WSUDOR_API_FIRE == True:
		print "Starting WSUDOR_API_app..."
		reactor.listenTCP( WSUDOR_API_LISTENER_PORT, WSUDOR_API_site )

	# fedConsumer
	if FEDCONSUMER_FIRE == True:
		print "Starting JSM listener..."
		indexer = IndexerWorker()
		indexer.run()


	print '''
                ::+:/`
         :----:+ssoo+:.`
      `-:+sssossysoooooo+/-`
    `:oysyo++ooooo+////+ooss+-`
   :ssyy/-`   `..     ..:/+osso:
 `/ssyo:                 `-+:oss+`
 +sso+:                    `//sss+
.sssoo`                     `o+sss:
/syso+                    `-`+ooss+
ssyoo+                    ../oossss
osso+o.                  `+//ooysoo
:ysyo+o.                  `/++osos:
`+ssssoo:`   ``.-` .-    `-ooosss+`
 `ossso///-.--:.``::. `.:+ooossso`
  `+sossyo++o++::///:/+ooossoss+`
    -ossssss+oo+sossoosossssso-
      ./osssssysyysssssssso/.
         `-:++sosyssyyo+:.

  <-- Ouroboros says hissss -->
	'''

	reactor.run()
