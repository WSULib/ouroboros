import json

from lib.imageServer.imageServerMain import imageWork
from lib.Projects.ProjectsMain import ProjectsMain


class mainRouter:	

	# class imports (need to have at runserver.py level)
	from fedoraConsumer import fedoraConsumer		

	# handles requests for images
	def imageServer(self,**kwargs):		
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
	


