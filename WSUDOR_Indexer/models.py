import json
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
import urllib
import xmltodict
import re

# celery
from celery import Task

# WSUDOR
import WSUDOR_ContentTypes
import WSUDOR_Manager
from WSUDOR_Manager import celery, db, fedora_handle
from WSUDOR_Manager.solrHandles import solr_handle
from WSUDOR_Manager.redisHandles import r_catchall
from WSUDOR_Indexer import logging

# localConfig
import localConfig



##################################################################################
# Fedora Java Messaging Service (JMS)
##################################################################################

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
			config = StompConfig(uri='tcp://%s:%s' % (localConfig.FEDCONSUMER_HOST, localConfig.FEDCONSUMER_PORT))
			config = StompConfig(uri='failover:(tcp://%s:%s)?randomize=false,startupMaxReconnectAttempts=3,initialReconnectDelay=5000,maxReconnectDelay=5000,maxReconnectAttempts=20' % (localConfig.FEDCONSUMER_HOST, localConfig.FEDCONSUMER_PORT))
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
			logging.debug("FedoraJMSConsumer: reconnecting")
			yield client.connect()

	def consume(self, client, frame):
		fedora_jms_worker = FedoraJMSWorker(frame)
		fedora_jms_worker.act()

	def error(self, connection, failure, frame, errorDestination):
		logging.debug("FedoraJMSConsumer: ERROR")
		logging.debug(failure)


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
		self.queue_action = False

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

		logging.debug("Fedora message: %s, consumed for: %s" % (self.methodName, self.pid))

		# debug
		logging.debug(self.headers)
		logging.debug(self.body)

		# capture modifications to datastream
		if self.methodName in ['addDatastream','modifyDatastreamByValue','modifyDatastreamByReference','purgeDatastream']:
			self._determine_ds()
			if self.ds not in localConfig.INDEXER_SKIP_DATASTREAMS:
				self.queue_action = 'index'

		# capture changes to object
		if self.methodName in ['modifyObject']:
			self.queue_action = 'index'

		# capture ingests
		if self.methodName in ['ingest']:
			self.queue_action = 'hold'

		# RDF relationships
		if self.methodName in ['addRelationship','purgeRelationship']:
			self.queue_action = 'index'

		# capture purge
		'''
		Perhaps unsurprisingly, this fails.
		When objects are purged, they cannot be opened to run their own .prune() method.
		Perhaps .prune() should be included here as well, so it can run seperate from object method?
		'''
		if self.methodName in ['purgeObject']:
			self.queue_action = 'prune'

		# finally, queue object and log
		if self.queue_action:
			self.queue_object()
			self.log_premis_event()


	def log_premis_event(self):

		# log PREMIS event
		PREMISWorker.log_jms_event.delay(self)


	def _determine_ds(self):
		'''
		Small function to determine which datastream was acted on
		'''
		self.ds = [c['@term'] for c in self.categories if c['@scheme'] == 'fedora-types:dsID'][0]
		logging.debug("datastream %s was acted on" % self.ds)
		return self.ds


	def queue_object(self):
		logging.debug("logging PREMIS event")
		IndexRouter.queue_object(self.pid, self.author, 1, self.queue_action)



##################################################################################
# Indexing / PREMIS
##################################################################################

# Indexer class
class IndexRouter(object):

	'''
	Class to handle polling and routing for WSUDOR_Indexer
	Most methods are classmethods, as they accept input and requests from various locales
	'''

	routable_actions = ['index','prune','forget']

	@classmethod
	def poll(self):

		db.session.close()

		# check working table load
		# working_count = indexer_working.query.count()
		# if working_count < 100:


		# refresh connection every poll
		query_results = indexer_queue.query \
			.filter(indexer_queue.timestamp < (datetime.now() - timedelta(seconds=localConfig.INDEXER_ROUTE_DELAY))) \
			.filter(indexer_queue.action.in_(self.routable_actions)) \
			.order_by(indexer_queue.priority.desc()) \
			.order_by(indexer_queue.timestamp.asc())
		
		# if result, push to router
		queue_rows = query_results.paginate(page=1, per_page=localConfig.INDEXER_POLL_CHUNK_SIZE).items
		for queue_row in queue_rows:
			if queue_row != None:
				self.route(queue_row)


	@classmethod
	def route(self, queue_row):
		
		'''
		Begins celery process, removes from queue
		'''
		
		logging.debug("IndexRouter: routing %s" % queue_row)
		
		# index object in solr
		if queue_row.action == 'index':
			if localConfig.INDEXER_AUTOINDEX:
				IndexWorker.index.delay(queue_row)
				self.dequeue_object(queue_row = queue_row)

		# prune object from solr
		elif queue_row.action == 'prune':
			if localConfig.INDEXER_AUTOINDEX:
				IndexWorker.prune.delay(queue_row)
				self.dequeue_object(queue_row = queue_row)

		# prune object from solr
		elif queue_row.action == 'forget':
			indexer_queue.query.filter_by(id=queue_row.id).delete()
			db.session.commit()

		# prune object from solr
		elif queue_row.action == 'hold':
			pass

		else:
			'''
			Is this necessary?  Or do we just want to skip unknown action by default and let them linger?
			'''
			logging.debug("IndexRouter: routing action `%s` not known, sending to exceptions" % queue_row.action)	
			self.add_exception(queue_row, dequeue=True)


	@classmethod
	def queue_object(self, pid, username, priority, action):

		'''
		if not in queue or working, add to queue
		'''

		# refresh
		db.session.close()

		# check if in working table
		if indexer_working.query.filter_by(pid = pid, action = action).count() == 0:

			logging.debug("IndexRouter: queuing %s, action %s" % (pid,action))
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

		else:
			logging.debug("IndexRouter: %s is currently in working, skipping queue" % pid)


	@classmethod
	def alter_queue_action(self, pid, action):
		# get row
		iqp = indexer_queue.query.filter_by(pid=pid).first()
		# alter status
		iqp.action = action
		# saved
		db.session.commit()


	@classmethod
	def dequeue_object(self, queue_row=None, pid=None, is_exception=False):
		'''
		moves object from queue to working
		'''
		try:
			if queue_row:
				logging.debug("IndexRouter: moving to working %s" % queue_row)
				indexer_queue.query.filter_by(id=queue_row.id).delete()
				working_tuple = (queue_row.pid, queue_row.username, queue_row.priority, queue_row.action)
				iwp = indexer_working(*working_tuple)
				db.session.add(iwp)
				db.session.commit()
				# if is_exception, add to exception table
				if is_exception:
					self.add_exception(queue_row, dequeue=False)
			elif pid:
				logging.debug("IndexRouter: dequeing %s" % pid)
				indexer_queue.query.filter_by(pid=pid).delete()
				db.session.commit()
		except:
			logging.warning("IndexRouter: Could not remove from queue, rolling back")
			db.session.rollback()


	@classmethod
	def object_complete(self, queue_row=None, is_exception=False, msg="Unknown"):
		'''
		removes from working table
		'''
		try:
			if queue_row:
				logging.debug("IndexRouter: marking as complete %s" % queue_row)
				indexer_working.query.filter_by(pid=queue_row.pid).delete()
				db.session.commit()
				# if is_exception, add to exception table
				if is_exception:
					self.add_exception(queue_row, dequeue=False, msg=msg)
		except:
			logging.warning("IndexRouter: Could not remove from queue, rolling back")
			db.session.rollback()

		# regardless bump, throughput count in redis		
		r_catchall.incr(int(time.time()), amount=1)

		
	@classmethod
	def add_exception(self, queue_row, dequeue=True, msg="Unknown"):
		logging.debug("IndexRouter: noting exception %s" % queue_row.pid)
		exception_tuple = (queue_row.pid, queue_row.username, queue_row.priority, queue_row.action, msg)
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
		if dequeue:
			self.dequeue_object(queue_row=queue_row)


	@classmethod	
	def remove_exception(self, pid, queue_row=None):
		if queue_row:
			pid = queue_row.pid
		logging.debug("IndexRouter: removing exception %s" % pid)
		indexer_exception.query.filter_by(pid=pid).delete()	
		db.session.commit()


	@classmethod	
	def queue_all_exceptions(self):
		db.session.execute('INSERT INTO indexer_queue (pid,username,priority,action,timestamp) (SELECT pid,username,priority,action,timestamp FROM `indexer_exception`);')
		indexer_exception.query.delete()
		db.session.commit()


	@classmethod	
	def clear_all_queues(self):
		indexer_queue.query.delete()
		indexer_working.query.delete()
		indexer_exception.query.delete()
		db.session.commit()


	@classmethod
	def last_index_date(self):
		doc_handle = WSUDOR_Manager.models.SolrDoc("LastFedoraIndex")
		return doc_handle.doc.solr_modifiedDate


	@classmethod
	def update_last_index_date(self):		
		doc_handle = WSUDOR_Manager.models.SolrDoc("LastFedoraIndex")
		doc_handle.doc.solr_modifiedDate = "NOW"
		result = doc_handle.update()
		return result.raw_content


	@classmethod
	def queue_modified(self, username=None, priority=1, action='index'):

		'''
		# Get Objects/Datastreams modified on or after this date
		# Returns streaming socket iterator with PIDs
		'''

		# index control objects
		self.queue_control()

		risearch_query = "select $object from <#ri> where $object <info:fedora/fedora-system:def/model#hasModel> <info:fedora/fedora-system:FedoraObject-3.0> and $object <fedora-view:lastModifiedDate> $modified and $modified <mulgara:after> '%s'^^<xml-schema:dateTime> in <#xsd>" % (self.last_index_date())

		risearch_params = urllib.urlencode({
			'type': 'tuples', 
			'lang': 'itql', 
			'format': 'CSV',
			'limit':'',
			'dt': 'on',
			'stream':'on',
			'query': risearch_query
			})
		risearch_host = "http://%s:%s@localhost/fedora/risearch?" % (localConfig.FEDORA_USER, localConfig.FEDORA_PASSWORD)

		modified_objects = urllib.urlopen(risearch_host,risearch_params)
		modified_objects.next() # bump past headers

		# for each in list, add to queue
		for pid in modified_objects:
			# skip control objectcs for queue_modified()
			if not re.match(r'%s' % localConfig.INDEXER_SKIP_PID_REGEX, pid.pid):
				self.queue_object(pid, username, priority, action)

		# set new last_index_date
		self.update_last_index_date()


	@classmethod
	def queue_collection(self, username=None, priority=1, action='index', collection_pid=False):

		sparql_query = 'select $pid from <#ri> where { $pid <info:fedora/fedora-system:def/relations-external#isMemberOfCollection> <%s> . }' % collection_pid
		logging.debug(sparql_query)
		collection_pids = fedora_handle.risearch.sparql_query(sparql_query)

		# for each in list, add to queue
		for pid in collection_pids:
			# skip control objectcs for queue_all()
			pid = pid['pid'].split("/")[-1]
			if not re.match(r'%s' % localConfig.INDEXER_SKIP_PID_REGEX, pid):
				self.queue_object(pid, username, priority, action)


	@classmethod
	def queue_all(self, username=None, priority=1, action='index'):

		# index control objects
		self.queue_control()

		# using sparql
		sparql_query = 'select $pid from <#ri> where { $pid <http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isWSUDORObject> "True" . }'		
		all_pids = fedora_handle.risearch.sparql_query(sparql_query)

		# for each in list, add to queue
		for pid in all_pids:
			# skip control objectcs for queue_all()
			pid = pid['pid'].split("/")[-1]
			if not re.match(r'%s' % localConfig.INDEXER_SKIP_PID_REGEX, pid):
				self.queue_object(pid, username, priority, action)

		# set new last_index_date
		self.update_last_index_date()


	@classmethod
	def queue_control(self, username=None, priority=2, action='index'):

		'''
		prioritize the indexing of "control" objects in Fedora that are 
		integral for indexing normal objects.
		'''
		# create ordered list of pids
		ordered_objs = []

		# content models
		ordered_objs.extend(list(fedora_handle.find_objects("CM:*")))

		# index collection objects
		ordered_objs.extend(list(fedora_handle.find_objects("wayne:collection*")))

		# ping solr to create set of versions for control objects
		s = solr_handle.search(**{'q':" OR ".join( ['id:%s' % obj.pid.replace(":","\:") for obj in ordered_objs] ),'fl':'_version_'})
		control_versions_set = {doc['_version_'] for doc in s.documents}

		# for each in list, add to queue
		for obj in ordered_objs:
			# skip control objectcs for queue_all()
			if not re.match(r'%s' % localConfig.INDEXER_SKIP_PID_REGEX, obj.pid):
				self.queue_object(obj.pid, username, priority, action)

		# compare versions of control objects in Solr, when all different, assumed committed
		count = 0
		while True:
			count += 1
			if count > 120:
				logging.debug('assuming control objects are indexing, breaking loop')
				break
			s = solr_handle.search(**{'q':" OR ".join( ['id:%s' % obj.pid.replace(":","\:") for obj in ordered_objs] ),'fl':'_version_'})
			check_set = {doc['_version_'] for doc in s.documents}
			commit_intersection = check_set.intersection(control_versions_set)
			logging.debug(check_set)
			logging.debug(control_versions_set)
			if len(commit_intersection) > 0 or len(check_set) == 0:
				logging.debug('control objects have not yet committed, checked %s times, still waiting' % (count))
				time.sleep(.5)
			else:
				logging.debug('control objects committed.')
				break



# Fires *after* task is complete
class postIndexWorker(Task):

	abstract = True

	def after_return(self, *args, **kwargs):

		# debug		
		logging.debug(args)

		queue_row = args[3][0]

		# if celery task completed, remove from working table
		if args[0] == 'SUCCESS':
			if args[1] == True:
				logging.debug("postIndexWorker: index success, removing from working %s" % queue_row)
				IndexRouter.object_complete(queue_row = queue_row)
			else:
				IndexRouter.object_complete(queue_row = queue_row, is_exception=True, msg=args[1])
		# dequeue and add exception
		else:
			logging.warning("postIndexWorker: index was not successful")
			IndexRouter.object_complete(queue_row = queue_row, is_exception=True, msg=args[1])


class IndexWorker(object):

	'''
	Class to perform indexing, modifying, and pruning of records in various systems (e.g. Solr)
	Each method expects queue_row as input.
	All methods are run as background celery tasks
		- when complete, fire post task cleanup
	'''

	@classmethod
	@celery.task(base=postIndexWorker, bind=True, max_retries=3, name="IndexWorker_index",trail=True)
	def index(self, queue_row):
		logging.debug("IndexWorker: indexing %s" % queue_row)
		obj = WSUDOR_ContentTypes.WSUDOR_Object(queue_row.pid)
		if obj:
			# remove from cache
			# obj.removeObjFromCache()
			# then, index
			index_result = obj.index()
			return index_result
		else:
			logging.warning("IndexWorker: could not open object, skipping")
			IndexRouter.dequeue_object(queue_row = queue_row, is_exception=True)
			return False


	@classmethod
	@celery.task(base=postIndexWorker, bind=True, max_retries=3, name="IndexWorker_prune",trail=True)
	def prune(self, queue_row):
		logging.debug("IndexWorker: pruning %s" % queue_row)
		obj = WSUDOR_ContentTypes.WSUDOR_Object(queue_row.pid)
		if obj:
			# remove from cache
			obj.removeObjFromCache()
			# then, prune
			return obj.prune()
		else:
			logging.warning("IndexWorker: could not open object, manually pruning from solr")
			solr_handle.delete_by_key(queue_row.pid)
			return True


	@classmethod
	# run this blocking, usually precedes queue_all() for reindex 
	def purge_all(self):
		logging.debug("IndexWorker: purging all documents in solr core")
		solr_handle.delete_by_query('*:*')
		return True


class PREMISWorker(object):

	'''
	Class to log PREMIS events for objects
	'''

	# method for logging PREMIS events when reported by Fedora JMS
	@staticmethod
	@celery.task(max_retries=3, name="log_jms_event", trail=True)
	def log_jms_event(jms_worker):

		# debugging
		logging.debug("PREMISWorker: logging event")

		# init PREMIS client
		premis_client = WSUDOR_Manager.models.PREMISClient(pid=jms_worker.pid.encode('utf-8'))

		# write event
		premis_client.add_jms_event(jms_worker)

		# save
		return premis_client.update()



##################################################################################
# Database Models
##################################################################################

# WSUDOR_Indexer queue table
class indexer_queue(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	pid = db.Column(db.String(255), unique=True)
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


class indexer_working(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	pid = db.Column(db.String(255), unique=True)
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
	pid = db.Column(db.String(255), unique=True)
	username = db.Column(db.String(255))
	priority = db.Column(db.Integer)
	action = db.Column(db.String(255))
	timestamp = db.Column(db.DateTime, default=datetime.now)
	msg = db.Column(db.String(2048))

	def __init__(self, pid, username, priority, action, msg):
		self.pid = pid
		self.username = username
		self.priority = priority
		self.action = action
		self.msg = msg

	def __repr__(self):
		return '<id %s, pid %s, priority %s, timestamp %s, username %s>' % (self.id, self.pid, self.priority, self.timestamp, self.username)



		


