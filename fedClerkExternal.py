# IMPORTS ################################################################
import json
import logging
from twisted.internet import reactor, defer
from twisted.internet.task import deferLater
from twisted.web.server import NOT_DONE_YET
from twisted.web import server, resource
from clerkRouter import clerkRouter 
from twisted.python import log

from localConfig import *  
        


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
        request.setHeader('Access-Control-Allow-Headers',
                           'x-prototype-version,x-requested-with')
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

        # send to clearkRouter, retrieve JSON string from WSUAPImain()
        worker = clerkRouter()
        # response = worker.imageServer(getParams=getParams)
        ###################################
        image_dict = worker.imageServer(getParams=getParams)
        ###################################

        # response 
        request.setHeader('Access-Control-Allow-Origin', '*')
        request.setHeader('Access-Control-Allow-Methods', 'GET, POST')
        request.setHeader('Access-Control-Allow-Headers',
                           'x-prototype-version,x-requested-with')
        request.setHeader('Access-Control-Max-Age', 2520)                
        request.setHeader('Content-Type', 'image/{mime}'.format(mime=image_dict['mime']))
        request.setHeader('Connection', 'Close')
        request.write(image_dict['img_binary'])
        request.finish()
        


    def render_GET(self, request):                
        d = deferLater(reactor, .01, lambda: request)
        d.addCallback(self._delayedImageServer)
        return NOT_DONE_YET
        




# Go
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)    
    reactor.listenTCP(WSUAPIListener_port, server.Site(WSUAPIListener()))
    reactor.listenTCP(imageServerListener_port, server.Site(imageServerListener()))
    reactor.run()







