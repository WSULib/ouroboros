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

import WSUDOR_Manager

# handles
from WSUDOR_Manager.solrHandles import solr_handle
from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager import redisHandles

# import WSUDOR_ContentTypes
import WSUDOR_ContentTypes


class WSUDOR_Image(WSUDOR_ContentTypes.WSUDOR_GenObject):

	def __init__(self,object_type=False,content_type=False,payload=False):
		
		# run __init__ from parent class
		WSUDOR_ContentTypes.WSUDOR_GenObject.__init__(self,object_type, content_type, payload)
		
		# Add WSUDOR_Image struct_requirements to WSUDOR_Object instance struct_requirements
		self.struct_requirements['WSUDOR_Image'] = {
			"datastreams":[
				{
					"id":"*_JP2",
					"purpose":"Fullsized, tiled JP2 version of the original image",
					"mimetype":"image/jp2"
				},
				{
					"id":"*_ACCESS",
					"purpose":"Fullsized JPEG of original",
					"mimetype":"image/jpeg"
				}
			],
			"external_relationships":[]
		}


	# perform ingestTest
	def validIngestBag(self):

		def report_failure(failure_tuple):
			if results_dict['verdict'] == True : results_dict['verdict'] = False
			results_dict['failed_tests'].append(failure_tuple)

		# reporting
		results_dict = {
			"verdict":True,
			"failed_tests":[]
		}


		# check that 'isRepresentedBy' datastream exists in self.objMeta.datastreams[]
		ds_ids = [each['ds_id'] for each in self.objMeta['datastreams']]
		if self.objMeta['isRepresentedBy'] not in ds_ids:
			report_failure(("isRepresentedBy_check","{isRep} is not in {ds_ids}".format(isRep=self.objMeta['isRepresentedBy'],ds_ids=ds_ids)))


		# check that content_type is a valid ContentType				
		if self.__class__ not in WSUDOR_ContentTypes.WSUDOR_GenObject.__subclasses__():
			report_failure(("Valid ContentType","WSUDOR_Object instance's ContentType: {content_type}, not found in acceptable ContentTypes: {ContentTypes_list} ".format(content_type=self.content_type,ContentTypes_list=WSUDOR_ContentTypes.WSUDOR_GenObject.__subclasses__())))


		# check that objMeta.id starts with "wayne:"
		# if not self.pid.startswith("wayne:"):
		# 	report_failure(("PID prefix","The pid {pid}, does not start with the usual 'wayne:' prefix.".format(pid=self.pid)))


		# check that objMeta.id is NOT already an object in WSUDOR
		# UPDATE : on back burner, Eulfedora seems to create a placeholder object in Fedora somehow...
		# ohandle = fedora_handle.get_object(self.pid)
		# if ohandle.exists == True:
		# 	report_failure(("PID existence in WSUDOR","The pid {pid}, appears to exist in WSUDOR already.".format(pid=self.pid)))						
		
		
		# finally, return verdict
		return results_dict


	# ingest image type
	def ingestBag(self):

		if self.object_type != "bag":
			raise Exception("WSUDOR_Object instance is not 'bag' type, aborting.")


		# attempt to ingest bag / object
		try:		
			
			self.ohandle = fedora_handle.get_object(self.objMeta['id'],create=True)
			self.ohandle.save()

			# set base properties of object
			self.ohandle.label = self.objMeta['label']

			# write POLICY datastream
			# NOTE: 'E' management type required, not 'R'
			print "Using policy:",self.objMeta['policy']
			policy_suffix = self.objMeta['policy'].split("info:fedora/")[1]
			policy_handle = eulfedora.models.DatastreamObject(self.ohandle,"POLICY", "POLICY", mimetype="text/xml", control_group="E")
			policy_handle.ds_location = "http://localhost/fedora/objects/{policy}/datastreams/POLICY_XML/content".format(policy=policy_suffix)
			policy_handle.label = "POLICY"
			policy_handle.save()

			# write objMeta as datastream
			objMeta_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "OBJMETA", "Ingest Bag Object Metadata", mimetype="application/json", control_group='M')
			objMeta_handle.label = "Ingest Bag Object Metadata"
			objMeta_handle.content = json.dumps(self.objMeta)
			objMeta_handle.save()

			# write explicit RELS-EXT relationships
			for pred_key in self.objMeta['object_relationships'].keys():
				self.ohandle.add_relationship(pred_key,self.objMeta['object_relationships'][pred_key])
			
			# writes derived RELS-EXT
			# isRepresentedBy
			self.ohandle.add_relationship("http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isRepresentedBy",self.objMeta['isRepresentedBy'])
			# hasContentModel
			content_type_string = "info:fedora/CM:"+self.objMeta['content_type'].split("_")[1]
			self.ohandle.add_relationship("info:fedora/fedora-system:def/relations-external#hasContentModel",content_type_string)

			# write MODS datastream
			objMeta_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "MODS", "MODS descriptive metadata", mimetype="text/xml", control_group='X')
			objMeta_handle.label = "MODS descriptive metadata"
			file_path = self.Bag.path + "/data/MODS.xml"
			objMeta_handle.content = open(file_path)
			objMeta_handle.save()

			# create derivatives and write datastreams
			for ds in self.objMeta['datastreams']:
				file_path = self.Bag.path + "/data/datastreams/" + ds['filename']
				print "Looking for:",file_path

				# original
				orig_handle = eulfedora.models.FileDatastreamObject(self.ohandle, ds['ds_id'], ds['label'], mimetype=ds['mimetype'], control_group='M')
				orig_handle.label = ds['label']
				orig_handle.content = open(file_path)
				orig_handle.save()
				
				# make thumb			
				temp_filename = "/tmp/Ouroboros/"+str(uuid.uuid4())+".jpg"
				im = Image.open(file_path)
				width, height = im.size
				max_width = 200	
				max_height = 200
				im.thumbnail((max_width, max_height), Image.ANTIALIAS)
				if im.mode != "RGB":
					im = im.convert("RGB")
				im.save(temp_filename,'JPEG')
				thumb_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "{ds_id}_THUMBNAIL".format(ds_id=ds['ds_id']), "{label}_THUMBNAIL".format(label=ds['label']), mimetype="image/jpeg", control_group='M')
				thumb_handle.label = "{label}_THUMBNAIL".format(label=ds['label'])
				thumb_handle.content = open(temp_filename)
				thumb_handle.save()
				os.system('rm {temp_filename}'.format(temp_filename=temp_filename))

				# make preview
				temp_filename = "/tmp/Ouroboros/"+str(uuid.uuid4())+".jpg"
				im = Image.open(file_path)
				width, height = im.size
				max_width = 1280	
				max_height = 960
				im.thumbnail((max_width, max_height), Image.ANTIALIAS)
				if im.mode != "RGB":
					im = im.convert("RGB")
				im.save(temp_filename,'JPEG')
				thumb_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "{ds_id}_PREVIEW".format(ds_id=ds['ds_id']), "{label}_PREVIEW".format(label=ds['label']), mimetype="image/jpeg", control_group='M')
				thumb_handle.label = "{label}_PREVIEW".format(label=ds['label'])
				thumb_handle.content = open(temp_filename)
				thumb_handle.save()
				os.system('rm {temp_filename}'.format(temp_filename=temp_filename))

				# make jp2
				temp_filename = "/tmp/Ouroboros/"+str(uuid.uuid4())+".jp2"
				os.system("convert {input} {output}[256x256]".format(input=file_path,output=temp_filename))
				thumb_handle = eulfedora.models.FileDatastreamObject(self.ohandle, "{ds_id}_JP2".format(ds_id=ds['ds_id']), "{label}_JP2".format(label=ds['label']), mimetype="image/jp2", control_group='M')
				thumb_handle.label = "{label}_JP2".format(label=ds['label'])
				thumb_handle.content = open(temp_filename)
				thumb_handle.save()
				os.system('rm {temp_filename}'.format(temp_filename=temp_filename))

				# add to RELS-INT
				fedora_handle.api.addRelationship(self.ohandle,'info:fedora/{pid}/{ds_id}'.format(pid=self.ohandle.pid,ds_id=ds['ds_id']),'info:fedora/fedora-system:def/relations-internal#isPartOf','info:fedora/{pid}'.format(pid=self.ohandle.pid))
				fedora_handle.api.addRelationship(self.ohandle,'info:fedora/{pid}/{ds_id}_THUMBNAIL'.format(pid=self.ohandle.pid,ds_id=ds['ds_id']),'info:fedora/fedora-system:def/relations-internal#isThumbnailOf','info:fedora/{pid}/{ds_id}'.format(pid=self.ohandle.pid,ds_id=ds['ds_id']))
				fedora_handle.api.addRelationship(self.ohandle,'info:fedora/{pid}/{ds_id}_JP2'.format(pid=self.ohandle.pid,ds_id=ds['ds_id']),'info:fedora/fedora-system:def/relations-internal#isJP2Of','info:fedora/{pid}/{ds_id}'.format(pid=self.ohandle.pid,ds_id=ds['ds_id']))
				fedora_handle.api.addRelationship(self.ohandle,'info:fedora/{pid}/{ds_id}_PREVIEW'.format(pid=self.ohandle.pid,ds_id=ds['ds_id']),'info:fedora/fedora-system:def/relations-internal#isPreviewOf','info:fedora/{pid}/{ds_id}'.format(pid=self.ohandle.pid,ds_id=ds['ds_id']))


			# write generic thumbnail and preview
			for gen_type in ['THUMBNAIL','PREVIEW']:
				thumb_rep_handle = eulfedora.models.DatastreamObject(self.ohandle,gen_type, gen_type, mimetype="image/jpeg", control_group="R")
				thumb_rep_handle.ds_location = "http://digital.library.wayne.edu/fedora/objects/{pid}/datastreams/{ds_id}_{gen_type}/content".format(pid=self.ohandle.pid,ds_id=self.objMeta['isRepresentedBy'],gen_type=gen_type)
				thumb_rep_handle.label = gen_type
				thumb_rep_handle.save()


			# save and commit object before finishIngest()
			final_save = self.ohandle.save()

			# finish generic ingest
			return self.finishIngest()



		# exception handling
		except Exception,e:
			print traceback.format_exc()
			print "Image Ingest Error:",e
			return False



























