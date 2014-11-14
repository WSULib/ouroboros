# module for management of bags in the WSUDOR environment
import bagit
import os
import mimetypes
import json
import uuid
import Image
import time
import traceback
import sys

# celery
from cl.cl import celery

# eulfedora
import eulfedora

# handles
from WSUDOR_Manager.solrHandles import solr_handle
from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager import redisHandles



class WSUDOR_Collection:
	
	# expects parent WSUDOR_Object as parameter
	def __init__(self,WSUDOR_Object):
		print WSUDOR_Object
		self.WSUDOR_Object = WSUDOR_Object


	# ingest image type
	def ingestBag(self):
		if self.WSUDOR_Object.objType != "bag":
			raise Exception("WSUDOR_Object instance is not 'bag' type, aborting.")		

		# ingest collection object
		try:			
			ohandle = fedora_handle.get_object(self.WSUDOR_Object.objMeta['id'],create=True)
			ohandle.save()

			# set base properties of object
			ohandle.label = self.WSUDOR_Object.objMeta['label']

			# write POLICY datastream (NOTE: 'E' management type required, not 'R')
			print "Using policy:",self.WSUDOR_Object.objMeta['policy']
			policy_suffix = self.WSUDOR_Object.objMeta['policy'].split("info:fedora/")[1]
			policy_handle = eulfedora.models.DatastreamObject(ohandle,"POLICY", "POLICY", mimetype="text/xml", control_group="E")
			policy_handle.ds_location = "http://localhost/fedora/objects/{policy}/datastreams/POLICY_XML/content".format(policy=policy_suffix)
			policy_handle.label = "POLICY"
			policy_handle.save()

			# write objMeta as datastream
			objMeta_handle = eulfedora.models.FileDatastreamObject(ohandle, "OBJMETA", "Ingest Bag Object Metadata", mimetype="application/json", control_group='M')
			objMeta_handle.label = "Ingest Bag Object Metadata"
			objMeta_handle.content = json.dumps(self.WSUDOR_Object.objMeta)
			objMeta_handle.save()

			# write explicit RELS-EXT relationships
			for pred_key in self.WSUDOR_Object.objMeta['object_relationships'].keys():
				ohandle.add_relationship(pred_key,self.WSUDOR_Object.objMeta['object_relationships'][pred_key])
			
			# writes derived RELS-EXT
			# isRepresentedBy
			ohandle.add_relationship("http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isRepresentedBy",self.WSUDOR_Object.objMeta['isRepresentedBy'])
			# hasContentModel
			content_type_string = "info:fedora/CM:"+self.WSUDOR_Object.objMeta['content_type'].split("_")[1]
			ohandle.add_relationship("info:fedora/fedora-system:def/relations-external#hasContentModel",content_type_string)

			# write MODS datastream
			objMeta_handle = eulfedora.models.FileDatastreamObject(ohandle, "MODS", "MODS descriptive metadata", mimetype="text/xml", control_group='X')
			objMeta_handle.label = "MODS descriptive metadata"
			file_path = self.WSUDOR_Object.Bag.path + "/data/MODS.xml"
			objMeta_handle.content = open(file_path)
			objMeta_handle.save()			

			# write generic thumbnail and preview
			for gen_type in ['THUMBNAIL','PREVIEW']:
				thumb_rep_handle = eulfedora.models.DatastreamObject(ohandle,gen_type, gen_type, mimetype="image/jpeg", control_group="R")
				thumb_rep_handle.ds_location = "http://digital.library.wayne.edu/fedora/objects/{pid}/datastreams/{ds_id}_{gen_type}/content".format(pid=ohandle.pid,ds_id=self.WSUDOR_Object.objMeta['isRepresentedBy'],gen_type=gen_type)
				thumb_rep_handle.label = gen_type
				thumb_rep_handle.save()

			# finally, save and commit object
			return ohandle.save()


			# for each bag in objects directory
			'''
			- write "info:fedora/fedora-system:def/relations-external#isMemberOfCollection" for each
			'''

		# exception handling
		except Exception,e:
			print traceback.format_exc()
			print "General Error:",e

		

		
