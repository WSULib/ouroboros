# library
from twisted.web.wsgi import WSGIResource
from twisted.web.server import Site
from twisted.internet import reactor
from twisted.internet.task import deferLater, LoopingCall
from twisted.web.server import NOT_DONE_YET
from twisted.web import server, resource
from twisted.python import log
import json
import logging
import subprocess

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
from WSUDOR_Indexer.models import FedoraJMSConsumer, Indexer


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

    # WSUDOR_Indexer
    if FEDCONSUMER_FIRE == True:
        print "Starting Fedora JSM consumer..."
        fedora_jms_consumer = FedoraJMSConsumer()
        fedora_jms_consumer.run()
        l = LoopingCall(Indexer.poll)
        l.start(INDEXER_POLL_DELAY)


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
