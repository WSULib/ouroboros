import xmltodict, json
import localConfig

# index to Solr
from WSUDOR_Manager.actions.solrIndexer import solrIndexer
from WSUDOR_Manager.actions.pruneSolr import pruneSolr_worker

# handles events in Fedora Commons as reported by JSM
class fedoraConsumer(object):

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
			if localConfig.SOLR_AUTOINDEX and self.ds != "DC":
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










