# -*- coding: utf-8 -*-

# python modules
import datetime
from lxml import etree
import time

# Ouroboros config
import localConfig

# Logging
from WSUDOR_API import logging

# WSUDOR_Manager
from WSUDOR_Manager import fedora_handle
from WSUDOR_Manager.solrHandles import solr_search_handle


# metadataPrefix map
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
			'rows': 5,
			'fq': [
				'rels_itemID:*',
				'rels_isMemberOfOAISet:"info\:fedora/wayne\:collectionDPLAOAI"'
			],
			'fl': [ 'id','rels_itemID'],
			'wt': 'json',
		}


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
		'''
		This is where the different verbs deviate
		'''
		self.verb_node = etree.Element(self.args['verb'])
		self.root_node.append(self.verb_node)


	def retrieve_records(self):
		'''
		1) depending on resumptionToken, ping solr for pids
		2) loop through pids, init OAIRecord for each, and append XML node from Eulfedora to self.verb_node
		'''

		# update search params
		# WILL DO HERE

		# fire search
		self.search_results = solr_search_handle.search(**self.search_params)

		# inti OAIRecord
		for i, doc in enumerate(self.search_results.documents):
			logging.info('adding record %s/%s, node: %s' % (i, self.search_results.total_results, doc['id']))
			record = OAIRecord(pid=doc['id'], itemID=doc['rels_itemID'], args=self.args)
			self.verb_node.append(record.oai_record_node)

		# finally, set resumption token
		self.set_resumption_token()


	def set_resumption_token(self):

		'''
		All of these values need updating
		'''

		# set resumption token node and attributes
		self.resumptionToken_node = etree.Element('resumptionToken')
		self.resumptionToken_node.attrib['expirationDate'] = "2017-05-11T14:43:12Z" # UPDATE
		self.resumptionToken_node.attrib['completeListSize'] = "44896" # UPDATE
		self.resumptionToken_node.attrib['cursor'] = "0" # UPDATE
		self.resumptionToken_node.text = 'THIS_IS_AN_AMAZING_TOKEN' # UPDATE
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

		if self.args['verb'] in verb_routes.keys():
			return verb_routes[self.args['verb']]()
		else:
			raise Exception("Verb not found.")


	# GetRecord
	def _GetRecord(self):
		pass


	# Identify
	def _Identify(self):
		pass


	# ListIdentifiers
	def _ListIdentifiers(self):
		pass


	# ListMetadataFormats
	def _ListMetadataFormats(self):
		pass


	# ListRecords
	def _ListRecords(self):

		self.scaffold()
		self.retrieve_records()
		return self.serialize()


	# ListSets
	def _ListSets(self):
		pass



class OAIRecord(object):

	'''
	Initialize OAIRecord with pid.
	
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
		self.itemID = itemID[0]
		self.args = args
		self.metadataPrefix = self.args['metadataPrefix']
		self.target_datastream = metadataPrefix_hash[self.metadataPrefix]
		self.oai_record_node = None

		# get metadata
		self.get_metadata()

		# build record node
		self.build_record_node()


	def get_metadata(self):

		# retrive metadata from Fedora
		self.fedora_object = fedora_handle.get_object(self.pid)
		self.metadata_datastream = self.fedora_object.getDatastreamObject(self.target_datastream)
		self.metadata_xml = self.metadata_datastream.content


	def build_record_node(self):

		# init node
		self.oai_record_node = etree.Element('record')

		# header node
		header_node = etree.Element('header')
		
		identifier_node = etree.Element('identifier')
		identifier_node.text = self.itemID
		header_node.append(identifier_node)

		datestamp_node = etree.Element('datestamp')
		datestamp_node.text = '2017-05-10' # UPDATE - when modified? can get this from eulfedora...
		header_node.append(datestamp_node)

		setSpec_node = etree.Element('setSpec')
		setSpec_node.text = self.args['set']
		header_node.append(setSpec_node)

		self.oai_record_node.append(header_node)

		# metadate node
		metadata_node = etree.Element('metadata')
		metadata_node.append(self.metadata_xml.node)
		self.oai_record_node.append(metadata_node)


def OAItest():

	# init OAIProvider
	op = OAIProvider({'verb':'ListRecords','set':'none','metadataPrefix':'mods'})

	# scaffold
	op.scaffold()

	# retrieve records
	op.retrieve_records()

	# serialize
	print op.serialize()
	



