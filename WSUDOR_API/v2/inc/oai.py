# -*- coding: utf-8 -*-

# python modules
import datetime
import json
from lxml import etree
import time
import hashlib

# Ouroboros config
import localConfig

# Logging
from WSUDOR_API import logging

# WSUDOR_Manager
from WSUDOR_Manager import fedora_handle, redisHandles
from WSUDOR_Manager.solrHandles import solr_search_handle


'''
ToDo

- resumption token
- other verbs
	- 
'''


# attempt to load metadataPrefix map from localConfig, otherwise default
if hasattr(localConfig,'OAI_METADATAPREFIX_HASH'):
	metadataPrefix_hash = localConfig.OAI_METADATAPREFIX_HASH
else:
	metadataPrefix_hash = {
		'mods':'MODS',
		'oai_dc':'DC',
		'dc':'DC'
	}


class OAIProvider(object):

	'''
	Initializing OAIProvider 
	This is because the OAI-PMH protocol shares verbs with reserved words in Python (e.g. "set", or "from").
	Easier to work with as a dictionary, and maintain the original OAI-PMH vocab.
	'''

	def __init__(self, args):
		self.args = args
		self.request_timestamp = datetime.datetime.now()

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
			self.search_params['fq'].append('rels_isMemberOfOAISet:"%s"' % self.args['set'].replace(":","\:"))

		# begin scaffolding
		self.scaffold()


	# generate XML root node with OAI-PMH scaffolding
	def scaffold(self):

		'''
		Target example:

		<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.openarchives.org/OAI/2.0/ http://www.openarchives.org/OAI/2.0/OAI-PMH.xsd">
		<responseDate>2017-05-11T13:43:11Z</responseDate>

			<request verb="ListRecords" set="wsudor_dpla" metadataPrefix="wsu_mods">http://metadata.library.wayne.edu/repox/OAIHandler</request>

			<VERB GOES HERE>

				<!-- record loop here -->
				<record>...</record>
				<record>...</record>

				<!-- resumptionToken -->
				<resumptionToken expirationDate="2017-05-11T14:43:12Z" completeListSize="44896" cursor="0">1494510192035:wsudor_dpla:wsu_mods:250:44896::</resumptionToken>
			</VERB ENDS HERE>
		</OAI-PMH>
		'''
		
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


	def set_resumption_token(self):

		'''
		All of these values need updating
		'''
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


	# serialize record nodes as XML response
	def serialize(self):
		return etree.tostring(self.root_node)


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

		# check for resumption token
		if self.args['resumptionToken']:
			logging.info('following resumption token, altering search_params')
			# retrieve token params and alter args and search_params
			resumption_params = json.loads(redisHandles.r_oai.get(self.args['resumptionToken']))
			self.args = resumption_params['args']
			self.search_params = resumption_params['search_params']

		if self.args['verb'] in verb_routes.keys():
			return verb_routes[self.args['verb']]()
		else:
			raise Exception("Verb not found.")


	######################################
	# OAI-PMH Verbs
	######################################

	# GetRecord
	def _GetRecord(self):
		
		# fire search
		self.search_params['q'] = 'rels_itemID:%s' % self.args['identifier'].replace(":","\:")
		self.search_results = solr_search_handle.search(**self.search_params)

		# check one result
		if self.search_results.total_results == 1:
			doc = self.search_results.documents[0]

			# init OAIRecord
			logging.info('retrieving node: %s' % (doc['id']))
			# init record
			record = OAIRecord(pid=doc['id'], itemID=doc['rels_itemID'][0], args=self.args)
			# include full metadata in record
			record.include_metadata()
			# append to verb_node
			self.verb_node.append(record.oai_record_node)

			return self.serialize()

		else:
			raise Exception("identifier not found")


	# Identify
	def _Identify(self):

		'''
		This can be filled out more...
		'''

		# init OAIRecord
		logging.info('generating identify node')
		
		# write Identify node
		description_node = etree.Element('description')
		description_node.text = 'WSUDOR, integrated OAI-PMH'
		self.verb_node.append(description_node)

		return self.serialize()


	# ListIdentifiers
	def _ListIdentifiers(self):

		# fire search
		self.search_results = solr_search_handle.search(**self.search_params)

		# inti OAIRecord
		for i, doc in enumerate(self.search_results.documents):
			logging.info('adding identifier %s/%s, node: %s' % (i, self.search_results.total_results, doc['id']))
			# init record
			record = OAIRecord(pid=doc['id'], itemID=doc['rels_itemID'][0], args=self.args)
			# append to verb_node
			self.verb_node.append(record.oai_record_node)

		# finally, set resumption token
		self.set_resumption_token()
		
		return self.serialize()


	# ListMetadataFormats
	def _ListMetadataFormats(self):
		pass


	# ListRecords
	def _ListRecords(self):

		# fire search
		self.search_results = solr_search_handle.search(**self.search_params)

		# inti OAIRecord
		for i, doc in enumerate(self.search_results.documents):
			logging.info('adding record %s/%s, node: %s' % (i, self.search_results.total_results, doc['id']))
			# init record
			record = OAIRecord(pid=doc['id'], itemID=doc['rels_itemID'][0], args=self.args)
			# include full metadata in record
			record.include_metadata()
			# append to verb_node
			self.verb_node.append(record.oai_record_node)

		# finally, set resumption token
		self.set_resumption_token()
		
		return self.serialize()


	# ListSets
	def _ListSets(self):
		pass



class OAIRecord(object):

	'''
	Initialize OAIRecord with pid and args
	
	Target XML schema:
	<header>
		<identifier>
		oai:digital.library.wayne.eduwsudor_dpla:oai:digital.library.wayne.edu:wayne:CFAIEB01c010
		</identifier>
		<datestamp>2017-05-10</datestamp>
		<setSpec>wsudor_dpla</setSpec>
	</header>
	<metadata>
		<mods:mods xmlns:mods="http://www.loc.gov/mods/v3" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="3.4" xsi:schemaLocation="http://www.loc.gov/mods/v3 http://www.loc.gov/standards/mods/v3/mods-3-4.xsd">
	</metadata>
	'''

	def __init__(self, pid=False, itemID=False, args=False):

		self.pid = pid
		self.itemID = itemID
		self.args = args
		self.metadataPrefix = self.args['metadataPrefix']
		self.target_datastream = metadataPrefix_hash[self.metadataPrefix]
		self.oai_record_node = None

		# get metadata
		self.get_metadata()

		# build record node
		self.init_record_node()


	def get_metadata(self):

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






