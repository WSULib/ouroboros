# module for management of bags in the WSUDOR environment
import bagit
import os
import mimetypes
import json
import uuid
from PIL import Image
import time
import traceback
import sys

# eulfedora
import eulfedora

import WSUDOR_Manager

# handles
from WSUDOR_Manager.solrHandles import solr_handle
from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager import redisHandles

# import WSUDORntentTypes
import WSUDOR_ContentTypes
from WSUDOR_ContentTypes import logging
logging = logging.getChild("WSUDOR_Object")


class WSUDOR_Volume(WSUDOR_ContentTypes.WSUDOR_GenObject):

	'''
	WSUDOR_Volume has no thumbnail.
	'''

	# static values for class
	label = "Volume"
	description = "Content Type for Volume Objects."
	Fedora_ContentType = "CM:Volume"
	version = 1

	def __init__(self,object_type=False,content_type=False,payload=False,orig_payload=False):
		
		# run __init__ from parent class
		WSUDOR_ContentTypes.WSUDOR_GenObject.__init__(self,object_type, content_type, payload, orig_payload)
		
		# Add WSUDOR_Image struct_requirements to WSUDOR_Object instance struct_requirements
		self.struct_requirements['WSUDOR_Volume'] = {
			"datastreams":[],
			"external_relationships":[]
		}

		# content-type methods run and returned to API
		self.public_api_additions = []

		# OAIexposed (on ingest, register OAI identifier)
		self.OAIexposed = False


	# perform ingestTest
	def validIngestBag(self):		
				
		# reporting
		results_dict = {
			"verdict":True,
			"failed_tests":[]
		}

		# finally, return verdict
		return results_dict


	# ingest
	def ingestBag(self, indexObject=True):
		if self.object_type != "bag":
			raise Exception("WSUDOR_Object instance is not 'bag' type, aborting.")		

		# ingest Volume object
		try:
			self.ohandle = fedora_handle.get_object(self.objMeta['id'],create=True)
			self.ohandle.save()

			# set base properties of object
			self.ohandle.label = self.objMeta['label']

			# write POLICY datastream (NOTE: 'E' management type required, not 'R')
			logging.debug("Using policy: %s" % self.objMeta['policy'])
			policy_suffix = self.objMeta['policy'].split("info:fedora/")[1]
			policy_handle = eulfedora.models.DatastreamObject(self.ohandle,"POLICY", "POLICY", mimetype="text/xml", control_group="E")
			policy_handle.ds_location = "http://localhost/fedora/objects/%s/datastreams/POLICY_XML/content" % (policy_suffix)
			policy_handle.label = "POLICY"
			policy_handle.save()

			# write objMeta as datastream
			objMeta_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "OBJMETA", "Ingest Bag Object Metadata", mimetype="application/json", control_group='M')
			objMeta_handle.label = "Ingest Bag Object Metadata"
			objMeta_handle.content = json.dumps(self.objMeta)
			objMeta_handle.save()

			# write explicit RELS-EXT relationships			
			for relationship in self.objMeta['object_relationships']:
				logging.debug("Writing relationship: %s %s" % (str(relationship['predicate']),str(relationship['object'])))
				self.ohandle.add_relationship(str(relationship['predicate']),str(relationship['object']))
					
			# writes derived RELS-EXT
			self.ohandle.add_relationship("http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isRepresentedBy",self.objMeta['isRepresentedBy'])
			content_type_string = "info:fedora/CM:"+self.objMeta['content_type'].split("_")[1]
			self.ohandle.add_relationship("info:fedora/fedora-system:def/relations-external#hasContentModel",content_type_string)

			# write MODS datastream if MODS.xml exists
			if os.path.exists(self.Bag.path + "/data/MODS.xml"):
				MODS_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "MODS", "MODS descriptive metadata", mimetype="text/xml", control_group='M')
				MODS_handle.label = "MODS descriptive metadata"
				file_path = self.Bag.path + "/data/MODS.xml"
				MODS_handle.content = open(file_path)
				MODS_handle.save()

			else:
				# write generic MODS datastream
				MODS_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "MODS", "MODS descriptive metadata", mimetype="text/xml", control_group='M')
				MODS_handle.label = "MODS descriptive metadata"

				raw_MODS = '''
<mods:mods xmlns:mods="http://www.loc.gov/mods/v3" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="3.4" xsi:schemaLocation="http://www.loc.gov/mods/v3 http://www.loc.gov/standards/mods/v3/mods-3-4.xsd">
  <mods:titleInfo>
	<mods:title>%s</mods:title>
  </mods:titleInfo>
  <mods:identifier type="local">%s</mods:identifier>
  <mods:extension>
	<PID>%s</PID>
  </mods:extension>
</mods:mods>
				''' % (self.objMeta['label'], self.objMeta['id'].split(":")[1], self.objMeta['id'])
				logging.debug("%s" % raw_MODS)
				MODS_handle.content = raw_MODS		
				MODS_handle.save()		

			# save and commit object before finishIngest()
			final_save = self.ohandle.save()
			
			# finish generic ingest
			return self.finishIngest(gen_manifest=False, indexObject=indexObject, contentTypeMethods=[])


		# exception handling
		except Exception,e:
			logging.debug("%s" % traceback.format_exc())
			logging.debug("Volume Ingest Error: %s" % e)
			return False

		

		

		
