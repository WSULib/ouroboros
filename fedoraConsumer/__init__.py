import xmltodict, json
from localConfig import *

# index to Solr
from WSUDOR_Manager.actions.solrIndexer import solrIndexer
from WSUDOR_Manager.actions.pruneSolr import pruneSolr_worker

# handles events in Fedora Commons as reported by JSM
def fedoraConsumer(self, **kwargs):			
	
	msg = kwargs['msg']
	print msg

	# create dictionary from XML string
	try:
		msgDict = xmltodict.parse(msg)

		# pull info
		fedEvent = msgDict['entry']['title']['#text']			

		# print fedEvent
		print "Action:",fedEvent

		# modify / add	
		if fedEvent.startswith("modify") or fedEvent.startswith("add"):
			PID = msgDict['entry']['category'][0]['@term']		
			print "Object PID:", PID

			# index to Solr if SOLR_AUTOINDEX is True
			if SOLR_AUTOINDEX == True:
				solrIndexer.delay(fedEvent,PID)

		# purge
		if fedEvent.startswith("purge"):
			PID = msgDict['entry']['category'][0]['@term']		
			print "Object PID:", PID
			pruneSolr_worker.delay(None,PID=PID)

		# ingest
		if fedEvent.startswith('ingest'):
			PID = msgDict['entry']['content']['#text']
			print "Object PID:", PID

			# index to Solr if SOLR_AUTOINDEX is True
			if SOLR_AUTOINDEX == True:
				solrIndexer.delay(fedEvent,PID)

	except Exception,e:
		print "Actions based on fedEvent failed or were not performed."
		print str(e)


