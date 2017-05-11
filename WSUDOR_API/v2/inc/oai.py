# -*- coding: utf-8 -*-

# python modules
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
		self.record_nodes = []


	# query and retrieve records
	def retrieve(self):
		pass


	# generate XML root node with OAI-PMH scaffolding
	'''
	Target example:

	<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.openarchives.org/OAI/2.0/ http://www.openarchives.org/OAI/2.0/OAI-PMH.xsd">
	<responseDate>2017-05-11T13:43:11Z</responseDate>

		<request verb="ListRecords" set="wsudor_dpla" metadataPrefix="wsu_mods">http://metadata.library.wayne.edu/repox/OAIHandler</request>

		<VERB GOES HERE>

			<!-- record loop here -->
			<record>
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
			</record>

			<!-- resumptionToken -->
			<resumptionToken expirationDate="2017-05-11T14:43:12Z" completeListSize="44896" cursor="0">1494510192035:wsudor_dpla:wsu_mods:250:44896::</resumptionToken>
		</VERB ENDS HERE>
	</OAI-PMH>
	'''
	def scaffold(self):
		
		# build root node, nsmap, and attributes		
		NSMAP = {
			None:'http://www.openarchives.org/OAI/2.0/'
		}
		self.root_node = etree.Element('OAI-PMH', nsmap=NSMAP)
		self.root_node.set('{http://www.w3.org/2001/XMLSchema-instance}schemaLocation', 'http://www.openarchives.org/OAI/2.0/ http://www.openarchives.org/OAI/2.0/OAI-PMH.xsd')

		# set verb node
		self.verb_node = etree.Element(self.args['verb'])
		self.root_node.append(self.verb_node)

		# set resumption token node and attributes
		self.resumptionToken_node = etree.Element('resumptionToken')
		self.resumptionToken_node.attrib['expirationDate'] = "2017-05-11T14:43:12Z"
		self.resumptionToken_node.attrib['completeListSize'] = "44896"
		self.resumptionToken_node.attrib['cursor'] = "0"
		self.resumptionToken_node.text = 'THIS_IS_AN_AMAZING_TOKEN'
		self.root_node.append(self.resumptionToken_node)


	# serialize record nodes as XML response
	def serialize(self):
		return etree.tostring(self.root_node)




class OAIRecord(object):

	'''
	Initialize OAIRecord with pid.
	Retrieves 
	'''

	def __init__(self, pid=False, metadataPrefix='mods'):
		self.pid = pid
		self.metadataPrefix = metadataPrefix
		self.target_datastream = metadataPrefix_hash[metadataPrefix]
		self.fedora_object = fedora_handle.get_object(pid)
		self.metadata_datastream = self.fedora_object.getDatastreamObject(self.target_datastream)
		self.metadata_xml = self.metadata_datastream.content


	def get_metadata(self):
		pass


def OAItest():

	# init OAIProvider
	op = OAIProvider({'verb':'ListRecords'})

	# scaffold
	op.scaffold()

	# serialize
	return op.serialize()
	



