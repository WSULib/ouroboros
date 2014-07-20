import xmltodict, json
from fedoraManager2.actions.FOXML2Solr import FOXML2Solr


# handles events in Fedora Commons as reported by JSM
def fedoraConsumer(self,**kwargs):			
	msg = kwargs['msg']		

	# create dictionary from XML string
	try:
		msgDict = xmltodict.parse(msg)
		# pull info
		fedEvent = msgDict['entry']['title']['#text']			

		# print fedEvent
		print "Action:",fedEvent

		# modify, purge
		if fedEvent.startswith("modify") or fedEvent.startswith("purge"):
			PID = msgDict['entry']['category'][0]['@term']		
			print "Object PID:", PID
			FOXML2Solr.delay(fedEvent,PID)

		# ingest
		if fedEvent.startswith('ingest'):
			PID = msgDict['entry']['content']['#text']
			print "Object PID:", PID
			FOXML2Solr.delay(fedEvent,PID)

	except Exception,e:
		print "Actions based on fedEvent failed or were not performed."
		print str(e)