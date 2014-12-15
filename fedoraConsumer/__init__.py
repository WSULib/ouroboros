import xmltodict, json
from WSUDOR_Manager.actions.solrIndexer import solrIndexer

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
		'''
		Improvement: Create list of actions in Fedora (probably API-M mostly) that will trigger event
		Improvement: Currently, only event is solrIndexer, but that could be extended.
		'''
		if fedEvent.startswith("modify") or fedEvent.startswith("purge") or fedEvent.startswith("add"):
			PID = msgDict['entry']['category'][0]['@term']		
			print "Object PID:", PID
			solrIndexer.delay(fedEvent,PID)

		# ingest
		if fedEvent.startswith('ingest'):
			PID = msgDict['entry']['content']['#text']
			print "Object PID:", PID
			solrIndexer.delay(fedEvent,PID)

	except Exception,e:
		print "Actions based on fedEvent failed or were not performed."
		print str(e)