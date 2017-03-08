import xmltodict, json
import localConfig
from stompest.async import Stomp
from stompest.async.listener import SubscriptionListener
from stompest.config import StompConfig
from stompest.protocol import StompSpec
from stompest.error import StompCancelledError, StompConnectionError, StompConnectTimeout, StompProtocolError
from twisted.internet import defer

# index to Solr
from WSUDOR_Manager.actions.solrIndexer import solrIndexer
from WSUDOR_Manager.actions.pruneSolr import pruneSolr_worker

# handles events in Fedora Commons as reported by JMS
class FedoraJMSConsumer(object):

	def __init__(self, frame):

		self.frame = frame
		self.headers = frame.headers
		self.methodName = self.headers['methodName']
		self.pid = self.headers['pid']
		self.ds = False
		self.body = frame.body
		self.parsed_body = xmltodict.parse(self.body)
		self.title = self.parsed_body['entry']['title']['#text']
		self.categories = self.parsed_body['entry']['category']

		# method type
		if self.methodName.startswith('add'):
			self.methodType = 'add'
		if self.methodName.startswith('modify'):
			self.methodType = 'modify'
		elif self.methodName.startswith('purge'):
			self.methodType = 'purge'
		else:
			self.methodType = False


	def act(self):

		print "Fedora message: %s, consumed for: %s" % (self.methodName, self.pid)

		# debug
		# print self.headers
		# print self.body

		# capture modifications to datastream
		if self.methodName in ['modifyDatastreamByValue','modifyDatastreamByReference']:
			self._determine_ds()
			if localConfig.SOLR_AUTOINDEX and self.ds not in localConfig.SKIP_INDEX_DATASTREAMS:
				self.index_object()

		# capture ingests
		if self.methodName in ['ingest']:
			if localConfig.SOLR_AUTOINDEX:
				self.index_object()

		# capture purge
		if self.methodName in ['purgeObject']:
			if localConfig.SOLR_AUTOINDEX:
				self.purge_object()


	def _determine_ds(self):
		'''
		Small function to determine which datastream was acted on
		'''
		self.ds = [c['@term'] for c in self.categories if c['@scheme'] == 'fedora-types:dsID'][0]
		print "datastream %s was acted on" % self.ds
		return self.ds


	def index_object(self):
		return solrIndexer.delay("fedoraConsumerIndex", self.pid)


	def purge_object(self):
		return pruneSolr_worker.delay(None,PID=self.pid)


# Fedora Commons Messaging STOMP protocol consumer ##############################################################
'''
Prod: Connected to JSM Messaging service on stomp://localhost:FEDCONSUMER_PORT (usually 61616),
routes 'fedEvents' to fedoraConsumer()

This needs some kind of listener if Tomcat (Fedora) goes down, it needs to reconnect...

'''
class FedoraJMSConsumer_Worker(object):


    QUEUE = "/topic/fedora.apim.update"
    ERROR_QUEUE = '/queue/testConsumerError'


    def __init__(self, config=None):
        if config is None:
            config = StompConfig('tcp://localhost:%s' % (localConfig.FEDCONSUMER_PORT))
            config = StompConfig(uri='failover:(tcp://localhost:%s)?randomize=false,startupMaxReconnectAttempts=3,initialReconnectDelay=5000,maxReconnectDelay=10000,maxReconnectAttempts=20' % (localConfig.FEDCONSUMER_PORT))
        self.config = config


    @defer.inlineCallbacks
    def run(self):
        client = Stomp(self.config)
        yield client.connect()
        headers = {
            # client-individual mode is necessary for concurrent processing
            StompSpec.ACK_HEADER: StompSpec.ACK_CLIENT_INDIVIDUAL,
            # the maximal number of messages the broker will let you work on at the same time
            'activemq.prefetchSize': '100',
        }
        try:
            client = yield client.disconnected
        except StompConnectionError:
            yield client.connect()
        client.subscribe(self.QUEUE, headers, listener=SubscriptionListener(self.consume))


    def consume(self, client, frame):
        fedora_jms_consumer = FedoraJMSConsumer(frame)
        fedora_jms_consumer.act()










