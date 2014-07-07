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

# local
from clerkRouter import clerkRouter
from localConfig import *

# import fedoraManger2 (fm2) app
from fedoraManager2 import app


# WSUDOR API ##############################################################
'''
Prod: Listening on :61617, reverseproxy in Apache to :80/WSUAPI.  Accepts GET parameters, routes to WSUAPI.py (formerly DCAPI project)
Dev: Listening on :61619
'''
class WSUAPIListener(resource.Resource):
	isLeaf = True

	# function for WSUAPI requests
	def _delayedWSUAPIRender(self,request):
		getParams = request.args

		# send to clearkRouter, retrieve JSON string from WSUAPImain()
		worker = clerkRouter()
		response = worker.WSUAPI(getParams=getParams)

		# response 
		request.setHeader('Access-Control-Allow-Origin', '*')
		request.setHeader('Access-Control-Allow-Methods', 'GET, POST')
		request.setHeader('Access-Control-Allow-Headers', 'x-prototype-version,x-requested-with')
		request.setHeader('Access-Control-Max-Age', 2520)
		request.setHeader("content-type", "application/json")
		request.setHeader('Connection', 'Close')
		request.setHeader('X-Powered-By', 'ShoppingHorse')
		request.write(response)
		request.finish()

	# function for unique and one-off modules
	def _delayedWSUAPIProjectsRender(self,request):
		getParams = request.args

		# send to clearkRouter, retrieve JSON string from WSUAPImain()
		worker = clerkRouter()
		response = worker.Projects(getParams=getParams,requestPath=request.path)

		# response 
		# iterate through header arguments        
		for k in response['headers']:
			request.setHeader(k,response['headers'][k])

		request.write(response['content'])
		request.finish()

	def render_GET(self, request):     
		print "Request path:",request.path
		d = deferLater(reactor, .01, lambda: request)                
		if "/projects/" in request.path:
			print "firing projects"
			d.addCallback(self._delayedWSUAPIProjectsRender)
		else:
			print "firing WSUAPI"
			d.addCallback(self._delayedWSUAPIRender)
		d.addErrback(log.err)
		return NOT_DONE_YET

	def render_POST(self, request):                
		d = deferLater(reactor, .01, lambda: request)        
		d.addCallback(self._delayedWSUAPIRender)
		d.addErrback(log.err)
		return NOT_DONE_YET
		


# WSU imageServer ##############################################################
'''
Prod: Listening on :61618
Dev: Listening on :61620
'''
class imageServerListener(resource.Resource):
	isLeaf = True

	def _delayedImageServer(self,request):
		getParams = request.args

		# send to clearkRouter
		worker = clerkRouter()
		# response = worker.imageServer(getParams=getParams)
		###################################
		image_dict = worker.imageServer(getParams=getParams)
		###################################

		# response 
		request.setHeader('Access-Control-Allow-Origin', '*')
		request.setHeader('Access-Control-Allow-Methods', 'GET, POST')
		request.setHeader('Access-Control-Allow-Headers','x-prototype-version,x-requested-with')
		request.setHeader('Access-Control-Max-Age', 2520)                
		request.setHeader('Content-Type', 'image/{mime}'.format(mime=image_dict['mime']))
		request.setHeader('Connection', 'Close')
		request.write(image_dict['img_binary'])
		request.finish()

	def render_GET(self, request):                
		d = deferLater(reactor, .01, lambda: request)
		d.addCallback(self._delayedImageServer)
		return NOT_DONE_YET


# Fedora Commons Messaging STOMP protocol consumer ##############################################################
'''
Prod: Connected to JSM Messaging service on :61616, routes 'fedEvents' to clerkRouter function from clerkRouter.py
Dev: Disabled
'''
class fedConsumer(object):
    QUEUE = "/topic/fedora.apim.update"
    def __init__(self, config=None):
        if config is None:
            config = StompConfig('tcp://localhost:61616')
        self.config = config

    @defer.inlineCallbacks
    def run(self):
        client = yield Stomp(self.config).connect()
        headers = {
            # client-individual mode is necessary for concurrent processing
            # (requires ActiveMQ >= 5.2)
            StompSpec.ACK_HEADER: StompSpec.ACK_CLIENT_INDIVIDUAL,
            # the maximal number of messages the broker will let you work on at the same time
            'activemq.prefetchSize': '100',
        }
        client.subscribe(self.QUEUE, headers, listener=SubscriptionListener(self.consume))

    def consume(self, client, frame):        

        #send to clearkRouter        
        worker = clerkRouter()
        worker.fedConsumer(msg=frame.body)



# twisted liseners
logging.basicConfig(level=logging.DEBUG)
resource = WSGIResource(reactor, reactor.getThreadPool(), app)
site = Site(resource)

if __name__ == '__main__':
	if fm2Fire == True:
		print "Starting fedoraManager2 server..."
		reactor.listenTCP( fedoraManager2_port, site )
	if WSUAPIFire == True:
		print "Starting WSUAPI..."
		reactor.listenTCP(WSUAPIListener_port, server.Site(WSUAPIListener()))
	if imageServerFire == True:
		print "Starting imageServer..."
		reactor.listenTCP(imageServerListener_port, server.Site(imageServerListener()))	
	if fedConsumerFire == True:
		print "Starting JSM listener..."
		fedConsumer().run()
	print "<--ouroboros says hissss-->"
	reactor.run()
