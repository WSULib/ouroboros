import xmltodict, json
from lib.FOXML2Solr.FOXML2Solr import FOXML2Solr
from lib.WSUAPI.WSUAPImain import WSUAPImain
from lib.eventNotify import eventNotify
from lib.imageServer.imageServerMain import imageWork
from lib.Projects.ProjectsMain import ProjectsMain

class clerkRouter:
	
	# handles events in Fedora Commons as reported by JSM
	def fedConsumer(self,**kwargs):		

		eventNotify.prettyPrint('fedEvent detected')
		msg = kwargs['msg']		

		# create dictionary from XML string
		try:
			msgDict = xmltodict.parse(msg)
			# pull info
			fedEvent = msgDict['entry']['title']['#text']			

			# testing, print results			
			print "Action:",fedEvent

			# modify, purge
			if fedEvent.startswith("modify") or fedEvent.startswith("purge"):
				PID = msgDict['entry']['category'][0]['@term']		
				print "Object PID:", PID
				FOXML2Solr(fedEvent,PID)
			# ingest
			if fedEvent.startswith('ingest'):
				PID = msgDict['entry']['content']['#text']
				print "Object PID:", PID
				FOXML2Solr(fedEvent,PID)

		except Exception,e:
			print "Actions based on fedEvent failed or were not performed."
			print str(e)		

	# handles WSUAPI requests
	def WSUAPI(self,**kwargs):
		eventNotify.prettyPrint('WSUAPI event detected')
		getParams = kwargs['getParams']

		# # run WSUAPImain(), return results to fedClerk
		try:			
			JSONstring = WSUAPImain(getParams)		
			return JSONstring
		except Exception,e:
			print "WSUAPI call unsuccessful.  Error:",str(e)
			return '{{"WSUAPIstatus":{exceptionErrorString}}}'.format(exceptionErrorString=json.dumps(str(e)))		

	# handles requests for images
	def imageServer(self,**kwargs):
		eventNotify.prettyPrint('imageServer request detected')
		getParams = kwargs['getParams']

		try:
			PILServ_response = imageWork(getParams)
			return PILServ_response
		except Exception,e:
			print "imageServer call unsuccessful.  Error:",str(e)
			return '{{"imageServerstatus":{exceptionErrorString}}}'.format(exceptionErrorString=json.dumps(str(e)))

	# handles events in Fedora Commons as reported by JSM
	def Projects(self,**kwargs):
		response = {}
		eventNotify.prettyPrint('Projects event detected')
		getParams = kwargs['getParams']
		requestPath = kwargs['requestPath']

		# # run WSUAPImain(), return results to fedClerk
		try:			
			response = ProjectsMain(getParams,requestPath)					
			return response
		except Exception,e:
			print "Projects call unsuccessful.  Error:",str(e)
			response['headers'] = {}
			response['headers']['Access-Control-Allow-Origin'] = '*'
			response['headers']['Access-Control-Allow-Methods'] = 'GET, POST'
			response['headers']['Access-Control-Allow-Headers'] = 'x-prototype-version,x-requested-with'
			response['headers']['Access-Control-Max-Age'] = 2520
			response['headers']["content-type"] = "application/json"
			response['headers']['Connection'] = 'Close'
			response['headers']['X-Powered-By'] = 'ShoppingHorse'
			response['content'] = '{{"WSUAPIstatus":{exceptionErrorString}}}'.format(exceptionErrorString=json.dumps(str(e)))
			return response
		


