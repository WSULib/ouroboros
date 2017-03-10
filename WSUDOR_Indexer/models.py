import xmltodict, json
import localConfig
from stompest.async import Stomp
from stompest.async.listener import SubscriptionListener
from stompest.config import StompConfig
from stompest.protocol import StompSpec
from stompest.error import StompCancelledError, StompConnectionError, StompConnectTimeout, StompProtocolError
from twisted.internet import defer
from datetime import datetime, timedelta
from sqlalchemy import UniqueConstraint
from sqlalchemy.exc import IntegrityError
import time

# index to Solr
from WSUDOR_Manager.actions.solrIndexer import solrIndexer
from WSUDOR_Manager.actions.pruneSolr import pruneSolr_worker

from WSUDOR_Manager import db

import logging



# Fedora JMS worker instantiated by Twisted
class FedoraJMSConsumer(object):

	'''
	Prod: Connected to JSM Messaging service on stomp://localhost:FEDCONSUMER_PORT (usually 61616),
	routes 'fedEvents' to fedoraConsumer()
	'''

	QUEUE = "/topic/fedora.apim.update"
	ERROR_QUEUE = '/queue/testConsumerError'

	def __init__(self, config=None):
		if config is None:
			config = StompConfig(uri='tcp://localhost:%s' % (localConfig.FEDCONSUMER_PORT))
			config = StompConfig(uri='failover:(tcp://localhost:%s)?randomize=false,startupMaxReconnectAttempts=3,initialReconnectDelay=5000,maxReconnectDelay=5000,maxReconnectAttempts=20' % (localConfig.FEDCONSUMER_PORT))
		self.config = config
		self.subscription_token = None


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

		client.subscribe(self.QUEUE, headers, listener=SubscriptionListener(self.consume, onMessageFailed=self.error))

		try:			
			client = yield client.disconnected
		except StompConnectionError:
			logging.info("FedoraJMSConsumer: reconnecting")
			yield client.connect()


	def consume(self, client, frame):
		fedora_jms_worker = FedoraJMSWorker(frame)
		fedora_jms_worker.act()

	def error(self, connection, failure, frame, errorDestination):
		logging.info("FedoraJMSConsumer: ERROR")
		logging.info(failure)


# handles events in Fedora Commons as reported by JMS
class FedoraJMSWorker(object):

	'''
	Worker that handles Fedora JMS messages captured by FedoraJMSConsumer
	'''

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

		logging.info("Fedora message: %s, consumed for: %s" % (self.methodName, self.pid))

		# debug
		# print self.headers
		# print self.body

		# capture modifications to datastream
		if self.methodName in ['modifyDatastreamByValue','modifyDatastreamByReference']:
			self._determine_ds()
			if self.ds not in localConfig.SKIP_INDEX_DATASTREAMS:
				self.index_object()

		# capture ingests
		if self.methodName in ['ingest']:
			self.index_object()

		# RDF relationships
		if self.methodName in ['addRelationship','purgeRelationship']:
			self.index_object()

		# capture purge
		if self.methodName in ['purgeObject']:
			self.purge_object()


	def _determine_ds(self):
		'''
		Small function to determine which datastream was acted on
		'''
		self.ds = [c['@term'] for c in self.categories if c['@scheme'] == 'fedora-types:dsID'][0]
		logging.debug("datastream %s was acted on" % self.ds)
		return self.ds


	# def index_object(self):
	# 	logging.info("FedoraJMSWorker: adding to queue")
	# 	queue_tuple = (self.pid, None, 1, 'index')
	# 	iqp = indexer_queue(*queue_tuple)
	# 	db.session.add(iqp)
	# 	try:
	# 		db.session.commit()
	# 	except:
	# 		db.session.rollback()


	# def purge_object(self):
	# 	logging.info("FedoraJMSWorker: adding to queue")
	# 	queue_tuple = (self.pid, None, 1, 'purge')
	# 	iqp = indexer_queue(*queue_tuple)
	# 	db.session.add(iqp)
	# 	try:
	# 		db.session.commit()
	# 	except:
	# 		db.session.rollback()

	def index_object(self):
		Indexer.queue_object(self.pid, None, 1, 'index')


	def purge_object(self):
		Indexer.queue_object(self.pid, None, 1, 'purge')


# Indexer class
class Indexer(object):

	'''
	Class to handle polling and indexing from SQL indexer_queue table
	'''

	@classmethod
	def poll(self):
		stime = time.time()
		queue_row = indexer_queue.query.filter(indexer_queue.timestamp < (datetime.now() - timedelta(seconds=localConfig.INDEXER_ROUTE_DELAY))).order_by(indexer_queue.priority.desc()).order_by(indexer_queue.timestamp.asc()).first()
		# if result, push to router
		if queue_row != None:			
			logging.info("Indexer: %s" % queue_row)
			self.queue_row = queue_row
			self._route()
		else:
			db.session.close()
		# logging.info("Indexer: polling elapsed: %s" % (time.time() - stime))


	@classmethod
	def _route(self):
		logging.info("Indexer: routing")
		
		# index object in solr
		if self.queue_row.action == 'index':
			if localConfig.SOLR_AUTOINDEX:
				self.index()

		# purge object from solr
		if self.queue_row.action == 'purge':
			if localConfig.SOLR_AUTOINDEX:
				self.purge()


	@classmethod
	def queue_object(self, pid, username, priority, action):
		logging.info("Indexer: adding to queue")
		queue_tuple = (pid, username, priority, action)
		iqp = indexer_queue(*queue_tuple)
		db.session.add(iqp)
		try:
			db.session.commit()
		except IntegrityError:
			logging.debug("Indexer: IntegrityError, pid likely exists, skipping and rolling back")
			db.session.rollback()
		except:
			logging.warning("Indexer: could not add to queue, rolling back")
			db.session.rollback()

	
	@classmethod
	def dequeue_object(self, pid=None):
		logging.info("Indexer: removing from queue")
		try:
			if pid == None:
				indexer_queue.query.filter_by(id=self.queue_row.id).delete()
			else:
				indexer_queue.query.filter_by(pid=pid).delete()
			db.session.commit()
		except:
			logging.warning("Indexer: Could not remove from queue, rolling back")
			db.session.rollback()


	@classmethod
	def index(self):
		logging.info("Indexer: indexing")
		solrIndexer.delay("WSUDOR_Indexer", self.queue_row.pid)
		self.dequeue_object()


	@classmethod
	def purge(self):
		logging.info("Indexer: purging")
		pruneSolr_worker.delay(None, PID=self.queue_row.pid)
		self.dequeue_object()



# WSUDOR_Indexer queue table
class indexer_queue(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	pid = db.Column(db.String(255), unique=True) # consider making this the primary key?
	username = db.Column(db.String(255))
	priority = db.Column(db.Integer)
	action = db.Column(db.String(255))
	timestamp = db.Column(db.DateTime, default=datetime.now)

	def __init__(self, pid, username, priority, action):
		self.pid = pid
		self.username = username
		self.priority = priority
		self.action = action

		from sqlalchemy import UniqueConstraint

	def __repr__(self):
		return '<id %s, pid %s, priority %s, timestamp %s, username %s>' % (self.id, self.pid, self.priority, self.timestamp, self.username)






