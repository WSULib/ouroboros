import json

from lib.imageServer.imageServerMain import imageWork


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



