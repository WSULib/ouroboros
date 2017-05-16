# -*- coding: utf-8 -*-

# python modules
from concurrent.futures.thread import ThreadPoolExecutor
import datetime
import hashlib
import json
from lxml import etree
import time

# Ouroboros config
import localConfig

# Logging
from WSUDOR_API import logging

# WSUDOR_Manager
from WSUDOR_Manager import fedora_handle, redisHandles
from WSUDOR_Manager.solrHandles import solr_search_handle


################################################################################################
# DEBUG FROM PROD
################################################################################################
# from mysolr import Solr
# solr_search_handle = Solr('http://digital.library.wayne.edu/solr4/fedobjs', version=4)
# from WSUDOR_Manager import fedoraHandles
# fedora_handle = fedoraHandles.remoteRepo('prod')
################################################################################################


# attempt to load metadataPrefix map from localConfig, otherwise provide default
if hasattr(localConfig,'OAI_METADATAPREFIX_HASH'):
	metadataPrefix_hash = localConfig.OAI_METADATAPREFIX_HASH
else:
	metadataPrefix_hash = {
		'mods':{
				'ds_id':'MODS',
				'schema':'http://www.loc.gov/standards/mods/v3/mods.xsd',
				'namespace':'http://www.loc.gov/mods/v3'
			},
		'oai_dc':{
				'ds_id':'DC',
				'schema':'http://www.openarchives.org/OAI/2.0/oai_dc.xsd',
				'namespace':'http://purl.org/dc/elements/1.1/'
			},
		'dc':{
				'ds_id':'DC',
				'schema':'http://www.openarchives.org/OAI/2.0/oai_dc.xsd',
				'namespace':'http://purl.org/dc/elements/1.1/'
			},
	}
inv_metadataPrefix_hash = {  metadataPrefix_hash[k]['ds_id']:{'prefix':k,'schema':metadataPrefix_hash[k]['schema'],'namespace':metadataPrefix_hash[k]['namespace']} for k in metadataPrefix_hash.keys() }


class OAIProvider(object):

	'''
	Initializing OAIProvider 
	This is because the OAI-PMH protocol shares verbs with reserved words in Python (e.g. "set", or "from").
	Easier to work with as a dictionary, and maintain the original OAI-PMH vocab.
	'''

	def __init__(self, args):

		self.args = args
		self.request_timestamp = datetime.datetime.now()
		self.record_nodes = []

		self.search_params = { 
			'q': '*:*',
			'sort': 'id asc',
			'start': 0,
			'rows': localConfig.OAI_RECORDS_PAGINATION,
			'fq': ['rels_itemID:*'],
			'fl': ['id','rels_itemID'],
			'wt': 'json',
		}

		# set set, if present
		if self.args['set']:
			self.search_params['fq'].append('rels_isMemberOfOAISet:"info:fedora/%s"' % self.args['set'].replace(":","\:"))

		# begin scaffolding
		self.scaffold()


	# generate XML root node with OAI-PMH scaffolding
	def scaffold(self):

		# build root node, nsmap, and attributes		
		NSMAP = {
			None:'http://www.openarchives.org/OAI/2.0/'
		}
		self.root_node = etree.Element('OAI-PMH', nsmap=NSMAP)
		self.root_node.set('{http://www.w3.org/2001/XMLSchema-instance}schemaLocation', 'http://www.openarchives.org/OAI/2.0/ http://www.openarchives.org/OAI/2.0/OAI-PMH.xsd')

		# set responseDate node
		'''
		<responseDate>2017-05-11T13:43:11Z</responseDate>
		'''
		self.responseDate_node = etree.Element('responseDate')
		self.responseDate_node.text = self.request_timestamp.strftime('%Y-%m-%dT%H:%M:%SZ')
		self.root_node.append(self.responseDate_node)
		
		# set request node
		'''
		<request verb="ListRecords" set="wsudor_dpla" metadataPrefix="wsu_mods">http://metadata.library.wayne.edu/repox/OAIHandler</request>
		'''
		self.request_node = etree.Element('request')
		self.request_node.attrib['verb'] = self.args['verb']
		if self.args['set']:
			self.request_node.attrib['set'] = self.args['set']
		if self.args['metadataPrefix']:
			self.request_node.attrib['metadataPrefix'] = self.args['metadataPrefix']
		self.request_node.text = 'http://digidev.library.wayne.edu/api/oai'
		self.root_node.append(self.request_node)

		# set verb node		
		self.verb_node = etree.Element(self.args['verb'])
		self.root_node.append(self.verb_node)


	def retrieve_records(self, include_metadata=False):

		'''
		asynchronous record retrieval from Fedora
		'''

		stime = time.time()
		logging.info("retrieving records for verb %s" % (self.args['verb']))

		# limit search to metadataPrefix provided
		if self.args['metadataPrefix'] in metadataPrefix_hash.keys():
			# self.search_params['fq'].append('obj_datastreams:%s' % metadataPrefix_hash[self.args['metadataPrefix']]['ds_id'] )
			self.search_params['fq'].append('admin_datastreams:*%s*' % metadataPrefix_hash[self.args['metadataPrefix']]['ds_id'] )
		elif not self.args['metadataPrefix']:
			return self.raise_error('cannotDisseminateFormat','metadataPrefix is required for verb: %s' % (self.args['verb']))
		else:
			return self.raise_error('cannotDisseminateFormat','The metadataPrefix %s is not allowed' % self.args['metadataPrefix'])

		# fire search
		logging.info(self.search_params)
		self.search_results = solr_search_handle.search(**self.search_params)
		logging.info(self.search_results.total_results)

		# if results none, and GetRecord
		if self.search_results.total_results == 0 and self.args['verb'] in ['GetRecord']:
			return self.raise_error('idDoesNotExist','The identifier %s is not found.' % self.args['identifier'])

		# if results none, and ListIdentifiers or ListRecords
		if self.search_results.total_results == 0 and self.args['verb'] in ['ListIdentifiers','ListRecords']:
			return self.raise_error('noRecordsMatch','No records were found.')

		with ThreadPoolExecutor(max_workers=5) as executor:
			for i, doc in enumerate(self.search_results.documents):
				executor.submit(self.record_thread_worker, doc, include_metadata)

		# add to verb node
		for oai_record_node in self.record_nodes:
			self.verb_node.append(oai_record_node)

		# finally, set resumption token
		self.set_resumption_token()

		# report
		etime = time.time()
		logging.info("%s record(s) returned in %sms" % (len(self.record_nodes), (float(etime) - float(stime)) * 1000))


	def record_thread_worker(self, doc, include_metadata):

		'''
		thread-based worker function for self.retrieve_records()
		'''

		record = OAIRecord(pid=doc['id'], itemID=doc['rels_itemID'][0], args=self.args)
		# include full metadata in record
		if include_metadata:
			 record.include_metadata()
		# append to record_nodes
		self.record_nodes.append(record.oai_record_node)
		return True


	def set_resumption_token(self):

		# set resumption token
		if self.search_params['start'] + self.search_params['rows'] < self.search_results.total_results:

			# prepare token
			token = hashlib.md5(self.request_timestamp.strftime('%Y-%m-%dT%H:%M:%SZ')).hexdigest()
			self.search_params['start'] = self.search_params['start'] + self.search_params['rows'] 
			redisHandles.r_oai.setex(token, 3600, json.dumps({'args':self.args,'search_params':self.search_params}))

			# set resumption token node and attributes
			self.resumptionToken_node = etree.Element('resumptionToken')
			self.resumptionToken_node.attrib['expirationDate'] = (self.request_timestamp + datetime.timedelta(0,3600)).strftime('%Y-%m-%dT%H:%M:%SZ')
			self.resumptionToken_node.attrib['completeListSize'] = str(self.search_results.total_results)
			self.resumptionToken_node.attrib['cursor'] = str(self.search_results.start)
			self.resumptionToken_node.text = token
			self.verb_node.append(self.resumptionToken_node)


	# convenience function to run all internal methods
	def generate_response(self):

		# read args, route verb to verb handler
		verb_routes = {
			'GetRecord':self._GetRecord,
			'Identify':self._Identify,
			'ListIdentifiers':self._ListIdentifiers,
			'ListMetadataFormats':self._ListMetadataFormats,
			'ListRecords':self._ListRecords,
			'ListSets':self._ListSets
		}

		# check verb
		if self.args['verb'] not in verb_routes.keys():
			return self.raise_error('badVerb','The verb %s is not allowed, must be GetRecord, Identify, ListIdentifiers, ListMetadataFormats, ListRecords, or ListSets' % self.args['verb'])

		# check for resumption token
		if self.args['resumptionToken']:
			logging.debug('following resumption token, altering search_params')
			# retrieve token params and alter args and search_params
			resumption_params_raw = redisHandles.r_oai.get(self.args['resumptionToken'])
			if resumption_params_raw is not None:
				resumption_params = json.loads()
				self.args = resumption_params['args']
				self.search_params = resumption_params['search_params']
			# raise error
			else:
				return self.raise_error('badResumptionToken', 'The resumptionToken %s is not found' % self.args['resumptionToken'])

		# fire verb reponse building
		verb_routes[self.args['verb']]()
		return self.serialize()


	def raise_error(self, error_code, error_msg):

		# remove verb node
		self.root_node.remove(self.verb_node)

		# create error node and append
		error_node = etree.SubElement(self.root_node, 'error')
		error_node.attrib['code'] = error_code
		error_node.text = error_msg

		# serialize and return
		return self.serialize()


	# serialize record nodes as XML response
	def serialize(self):
		return etree.tostring(self.root_node)


	# GetRecord
	def _GetRecord(self):
		
		self.search_params['q'] = 'rels_itemID:%s' % self.args['identifier'].replace(":","\:")
		self.retrieve_records(include_metadata=True)


	# Identify
	def _Identify(self):

		# init OAIRecord
		logging.debug('generating identify node')
		
		# write Identify node
		description_node = etree.Element('description')
		description_node.text = 'WSUDOR, integrated OAI-PMH'
		self.verb_node.append(description_node)


	# ListIdentifiers
	def _ListIdentifiers(self):

		self.retrieve_records()


	# ListMetadataFormats
	def _ListMetadataFormats(self):

		'''
		List all metadataformats, or optionally, available metadataformats for one item based on datastreams
		'''

		if self.args['identifier']:
			try:
				logging.debug("identifier provided for ListMetadataFormats, confirming that identifier exists...")
				search_results = solr_search_handle.search(**{'q':'rels_itemID:%s' % self.args['identifier'].replace(":","\:"),'fl':['id']})
				if search_results.total_results > 0:
					fedora_object = fedora_handle.get_object(search_results.documents[0]['id'])
					if fedora_object.exists:
						logging.info("record found, returning allowed metadataPrefixs")
						for ds in fedora_object.ds_list:
							if ds in inv_metadataPrefix_hash.keys():

								mf_node = etree.Element('metadataFormat')

								# write metadataPrefix node
								prefix = etree.SubElement(mf_node,'metadataPrefix')
								prefix.text = inv_metadataPrefix_hash[ds]['prefix']

								# write schema node
								schema = etree.SubElement(mf_node,'schema')
								schema.text = inv_metadataPrefix_hash[ds]['schema']

								# write schema node
								namespace = etree.SubElement(mf_node,'metadataNamespace')
								namespace.text = inv_metadataPrefix_hash[ds]['namespace']

								# append to verb_node and return
								self.verb_node.append(mf_node)
					else:
						raise Exception('record could not be located')		
				else:
					raise Exception('record could not be located')
			except:
				return self.raise_error('idDoesNotExist','The identifier %s is not found.' % self.args['identifier'])
			
		else:
			# iterate through available metadataFormats and return
			for mf in metadataPrefix_hash.keys():

				mf_node = etree.Element('metadataFormat')

				# write metadataPrefix node
				prefix = etree.SubElement(mf_node,'metadataPrefix')
				prefix.text = mf

				# write schema node
				schema = etree.SubElement(mf_node,'schema')
				schema.text = metadataPrefix_hash[mf]['schema']

				# write schema node
				namespace = etree.SubElement(mf_node,'metadataNamespace')
				namespace.text = metadataPrefix_hash[mf]['namespace']

				# append to verb_node and return
				self.verb_node.append(mf_node)


	# ListRecords
	def _ListRecords(self):

		self.retrieve_records(include_metadata=True)


	# ListSets
	def _ListSets(self):

		# get collections
		search_results = solr_search_handle.search(**{
				'q':'*:*',
				'fq':['rels_itemID:*','rels_hasContentModel:*Collection'],
				'fl':['id','rels_itemID','dc_title']
			})

		# generate response
		for oai_set in search_results.documents:
			set_node = etree.Element('set')
			setSpec = etree.SubElement(set_node,'setSpec')
			setSpec.text = oai_set['id']
			setName = etree.SubElement(set_node,'setName')
			setName.text = oai_set['dc_title'][0]
			self.verb_node.append(set_node)



class OAIRecord(object):

	'''
	Initialize OAIRecord with pid and args
	'''

	def __init__(self, pid=False, itemID=False, args=False):

		self.pid = pid
		self.itemID = itemID
		self.args = args
		self.metadataPrefix = self.args['metadataPrefix']
		self.target_datastream = metadataPrefix_hash[self.metadataPrefix]['ds_id']
		self.oai_record_node = None

		# get metadata
		self.get_fedora_object()

		# build record node
		self.init_record_node()


	def get_fedora_object(self):

		# retrive metadata from Fedora
		self.fedora_object = fedora_handle.get_object(self.pid)
		self.metadata_datastream = self.fedora_object.getDatastreamObject(self.target_datastream)
		self.metadata_xml = self.metadata_datastream.content


	def init_record_node(self):

		# init node
		self.oai_record_node = etree.Element('record')

		# header node
		header_node = etree.Element('header')
		
		identifier_node = etree.Element('identifier')
		identifier_node.text = self.itemID
		header_node.append(identifier_node)

		datestamp_node = etree.Element('datestamp')
		datestamp_node.text = self.metadata_datastream.last_modified().strftime('%Y-%m-%d')
		header_node.append(datestamp_node)

		if self.args['set']:
			setSpec_node = etree.Element('setSpec')
			setSpec_node.text = self.args['set']
			header_node.append(setSpec_node)

		self.oai_record_node.append(header_node)


	def include_metadata(self):

		# metadate node
		metadata_node = etree.Element('metadata')
		metadata_node.append(self.metadata_xml.node)
		self.oai_record_node.append(metadata_node)






