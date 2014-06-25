# IMPORTS ################################################################
import json
import logging
from twisted.internet import reactor, defer
from twisted.internet.task import deferLater
from twisted.web.server import NOT_DONE_YET
from twisted.web import server, resource
from stompest.async import Stomp
from stompest.async.listener import SubscriptionListener
from stompest.config import StompConfig
from stompest.protocol import StompSpec
from clerkRouter import clerkRouter 

from localConfig import *


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

# Go
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    if fedConsumerFire == True: #check localConfig.py for fedConsumerFire True/False
        fedConsumer().run()        
        reactor.run()
    else:
        exit()







