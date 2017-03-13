import xmltodict, json
import localConfig
from stompest.async import Stomp
from stompest.async.listener import SubscriptionListener
from stompest.config import StompConfig
from stompest.protocol import StompSpec
from stompest.error import StompCancelledError, StompConnectionError, StompConnectTimeout, StompProtocolError
from twisted.internet import reactor, defer
from datetime import datetime, timedelta
from sqlalchemy import UniqueConstraint
from sqlalchemy.exc import IntegrityError
import time

from WSUDOR_Manager.actions.solrIndexer import solrIndexer
from WSUDOR_Manager.actions.pruneSolr import pruneSolr_worker
from WSUDOR_Manager import solrHandles
import WSUDOR_ContentTypes

from WSUDOR_Manager import db

import logging

# celery



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
		self.author = self.parsed_body['entry']['author']['name']

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
				self.queue_action = 'index'
				self.queue_object()

		# capture ingests
		if self.methodName in ['ingest']:
			self.queue_action = 'index'
			self.queue_object()

		# RDF relationships
		if self.methodName in ['addRelationship','purgeRelationship']:
			self.queue_action = 'index'
			self.queue_object()

		# capture purge
		if self.methodName in ['purgeObject']:
			self.queue_action = 'purge'
			self.queue_object()


	def _determine_ds(self):
		'''
		Small function to determine which datastream was acted on
		'''
		self.ds = [c['@term'] for c in self.categories if c['@scheme'] == 'fedora-types:dsID'][0]
		logging.debug("datastream %s was acted on" % self.ds)
		return self.ds


	def queue_object(self):
		IndexRouter.queue_object(self.pid, self.author, 1, self.queue_action)


# Indexer class
class IndexRouter(object):

	'''
	Class to handle polling and routing of index queue
	Most methods are classmethods, as they accept input and requests from various endpoints

	Preferred workflow for indexing items is:
		1) item added to queue with queue_object()
		2) poll() and route() pick it up, sending to IndexWorker as queue_row, which includes pid and action
	'''

	@classmethod
	def poll(self):
		stime = time.time()
		queue_row = indexer_queue.query.filter(indexer_queue.timestamp < (datetime.now() - timedelta(seconds=localConfig.INDEXER_ROUTE_DELAY))).order_by(indexer_queue.priority.desc()).order_by(indexer_queue.timestamp.asc()).first()
		# if result, push to router
		if queue_row != None:			
			self.route(queue_row)
		else:
			db.session.close()
		# logging.info("Indexer: polling elapsed: %s" % (time.time() - stime))


	@classmethod
	def route(self, queue_row):
		logging.info("IndexRouter: routing %s" % queue_row)
		
		# index object in solr
		if queue_row.action == 'index':
			if localConfig.SOLR_AUTOINDEX:
				iw = IndexWorker(queue_row)
				iw.index()

		# purge object from solr
		if queue_row.action == 'purge':
			if localConfig.SOLR_AUTOINDEX:
				iw = IndexWorker(queue_row)
				iw.purge()


	@classmethod
	def queue_object(self, pid, username, priority, action):
		logging.info("IndexRouter: queuing %s" % pid)
		queue_tuple = (pid, username, priority, action)
		iqp = indexer_queue(*queue_tuple)
		db.session.add(iqp)
		try:
			db.session.commit()
		except IntegrityError:
			logging.debug("IndexRouter: IntegrityError, pid likely exists, skipping and rolling back")
			db.session.rollback()
		except:
			logging.warning("IndexRouter: could not add to queue, rolling back")
			db.session.rollback()

	
	@classmethod
	def dequeue_object(self, queue_row=None, pid=None, is_exception=False):
		try:
			if queue_row:
				logging.info("IndexRouter: dequeing %s" % queue_row)
				indexer_queue.query.filter_by(id=queue_row.id).delete()
				db.session.commit()
				# if is_exception, add to exception table
				if is_exception:
					self.add_exception(queue_row.pid, queue_row.username, queue_row.priority, queue_row.action)
				# # else, assume success and remove from exceptions if present
				# else:
				# 	self.remove_exception(queue_row=queue_row)
			elif pid:
				logging.info("IndexRouter: dequeing %s" % pid)
				indexer_queue.query.filter_by(pid=pid).delete()
				db.session.commit()
		except:
			logging.warning("IndexRouter: Could not remove from queue, rolling back")
			db.session.rollback()

		
	@classmethod
	def add_exception(self, pid, username, priority, action):
		logging.info("IndexRouter: noting exception %s" % pid)
		exception_tuple = (pid, username, priority, action)
		exception = indexer_exception(*exception_tuple)
		db.session.add(exception)
		try:
			db.session.commit()
		except IntegrityError:
			logging.debug("IndexRouter: IntegrityError, pid likely exists, skipping and rolling back")
			db.session.rollback()
		except:
			logging.warning("IndexRouter: could not add to exceptions, rolling back")
			db.session.rollback()


	@classmethod	
	def remove_exception(self, pid, queue_row=None):
		if queue_row:
			pid = queue_row.pid
		logging.info("IndexRouter: removing exception %s" % pid)
		indexer_exception.query.filter_by(pid=pid).delete()	
		db.session.commit()


	@classmethod	
	def queue_exceptions(self):
		
		# indexer_queue.__table__.insert().from_select(names=['pid','username','priority','action'],select=db.session.query(indexer_exception))
		db.session.execute('INSERT INTO indexer_queue (pid,username,priority,action,timestamp) (SELECT pid,username,priority,action,timestamp FROM `indexer_exception`);')
		indexer_exception.query.delete()
		db.session.commit()



class IndexWorker(object):

	'''
	Class to perform indexing, modifying, and purging of records in various systems (e.g. Solr)
	When initialized, expects queue_row as input
	'''

	def __init__(self, queue_row):
		self.queue_row = queue_row


	def index(self):
		logging.info("IndexWorker: indexing %s" % self.queue_row)
		obj = WSUDOR_ContentTypes.WSUDOR_Object(self.queue_row.pid)
		if obj:
			index_result = obj.index()
			if index_result:
				IndexRouter.dequeue_object(queue_row = self.queue_row)
			else:
				logging.warning("IndexWorker: index was not successful")
				IndexRouter.dequeue_object(queue_row = self.queue_row, is_exception=True)
		else:
			logging.warning("IndexWorker: could not open object, skipping")
			IndexRouter.dequeue_object(queue_row = self.queue_row, is_exception=True)


	def purge(self):
		logging.info("IndexWorker: purging %s" % self.queue_row)
		pruneSolr_worker.delay(None, PID=self.queue_row.pid)
		IndexRouter.dequeue_object(queue_row = self.queue_row)



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

	def __repr__(self):
		return '<id %s, pid %s, priority %s, timestamp %s, username %s>' % (self.id, self.pid, self.priority, self.timestamp, self.username)


class indexer_exception(db.Model):
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

	def __repr__(self):
		return '<id %s, pid %s, priority %s, timestamp %s, username %s>' % (self.id, self.pid, self.priority, self.timestamp, self.username)






