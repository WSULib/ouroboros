# module for management of bags in the WSUDOR environment
import bagit
import os
import mimetypes
import json
import uuid
import Image

# celery
from cl.cl import celery

# eulfedora
import eulfedora

# handles
from WSUDOR_Manager.solrHandles import solr_handle
from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager import redisHandles


class WSUDOR_Image:

	# expects parent WSUDOR_Object as parameter
	def __init__(self,WSUDOR_Object):
		print WSUDOR_Object
		self.WSUDOR_Object = WSUDOR_Object

	# ingest image type
	def ingestBag(self):
		'''
		Can this itWSUDOR_Object fire a job?
		Like, 3/10 stages complete, etc.
		'''
		
		# DEBUG
		try:
			fedora_handle.purge_object('wayne:BAGTESTtree1')
			print "object purged"
		except:
			print "Object not found in Fedora, no need to purge."

		# create object
		ohandle = fedora_handle.get_object(self.WSUDOR_Object.objMeta['id'], create=True)
		ohandle.label = self.WSUDOR_Object.objMeta['label']
		# commit it, requisite for writing datastreams below
		ohandle.save()

		# write POLICY datastream
		# NOTE: 'E' management type required, not 'R'
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

		# write RELS-EXT relationships
		for pred_key in self.WSUDOR_Object.objMeta['object_relationships'].keys():
			ohandle.add_relationship(pred_key,self.WSUDOR_Object.objMeta['object_relationships'][pred_key])

		# write MODS datastream
		objMeta_handle = eulfedora.models.FileDatastreamObject(ohandle, "MODS", "MODS descriptive metadata", mimetype="text/xml", control_group='X')
		objMeta_handle.label = "MODS descriptive metadata"
		file_path = self.WSUDOR_Object.Bag.path + "/data/MODS.xml"
		objMeta_handle.content = open(file_path)
		objMeta_handle.save()

		# create derivatives and write datastreams
		for ds in self.WSUDOR_Object.objMeta['datastreams']:
			file_path = self.WSUDOR_Object.Bag.path + "/data/datastreams/" + ds['filename']
			print "Looking for:",file_path

			# original
			orig_handle = eulfedora.models.FileDatastreamObject(ohandle, ds['ds_id'], ds['label'], mimetype=ds['mimetype'], control_group='M')
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
			thumb_handle = eulfedora.models.FileDatastreamObject(ohandle, "{ds_id}_THUMBNAIL".format(ds_id=ds['ds_id']), "{label}_THUMBNAIL".format(label=ds['label']), mimetype="image/jpeg", control_group='M')
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
			thumb_handle = eulfedora.models.FileDatastreamObject(ohandle, "{ds_id}_PREVIEW".format(ds_id=ds['ds_id']), "{label}_PREVIEW".format(label=ds['label']), mimetype="image/jpeg", control_group='M')
			thumb_handle.label = "{label}_PREVIEW".format(label=ds['label'])
			thumb_handle.content = open(temp_filename)
			thumb_handle.save()
			os.system('rm {temp_filename}'.format(temp_filename=temp_filename))

			# make jp2
			temp_filename = "/tmp/Ouroboros/"+str(uuid.uuid4())+".jp2"
			os.system("convert {input} {output}[256x256]".format(input=file_path,output=temp_filename))
			thumb_handle = eulfedora.models.FileDatastreamObject(ohandle, "{ds_id}_JP2".format(ds_id=ds['ds_id']), "{label}_JP2".format(label=ds['label']), mimetype="image/jp2", control_group='M')
			thumb_handle.label = "{label}_JP2".format(label=ds['label'])
			thumb_handle.content = open(temp_filename)
			thumb_handle.save()
			os.system('rm {temp_filename}'.format(temp_filename=temp_filename))


		# write RELS-INT

		# finally, save and commit object
		return ohandle.save()