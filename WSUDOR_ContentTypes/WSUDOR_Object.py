# module for management of bags in the WSUDOR environment
import bagit
import os
import mimetypes
import json
import Image
import uuid
import StringIO

# celery
from cl.cl import celery

# eulfedora
import eulfedora

# handles
from WSUDOR_Manager.solrHandles import solr_handle
from WSUDOR_Manager.fedoraHandles import fedora_handle
from WSUDOR_Manager import redisHandles

'''
Would be possible to combine these, just with an arg flag
See this for inspiration: https://github.com/emory-libraries/eulfedora/blob/5916c0cf8d30247ec5cfe04803089c275cdf15da/eulfedora/models.py
'''

class WSUDOR_Object:

	'''
	This class represents an object already present, or destined, for Ouroboros.  
	"objType" is required for discerning between the two.

	objType = 'WSUDOR'
		- object is present in WSUDOR, actions include management and export

	objType = 'bag'
		- object is present outside of WSUDOR, actions include primarily ingest and validation
	'''

	# init
	def __init__(self,objType=False,bag_dir=False,eulfedoraObject=False):
		
		if objType == "bag":
			# read objMeta.json
			path = bag_dir + '/data/objMeta.json'
			fhand = open(path,'r')
			self.objMeta = json.loads(fhand.read())
			print "objMeta.json loaded for:",self.objMeta['id'],"/",self.objMeta['label']

			# BagIt methods
			self.Bag = bagit.Bag(bag_dir)


		if objType == "WSUDOR":
			self.pid = eulfedoraObject.pid
			self.pid_suffix = eulfedoraObject.pid.split(":")[1]
			self.ohandle = eulfedoraObject

			#######################################
			# MOVE TO SOMEWHERE CENTRAL		
			#######################################
			# import WSUDOR opinionated mimes
			opinionated_mimes = {
				# images
				"image/jp2":".jp2"		
			}	

			# push to mimetypes.types_map
			for k, v in opinionated_mimes.items():
				# reversed here
				mimetypes.types_map[v] = k
			#######################################


	# export WSUDOR objectBag
	def exportBag(self):
		'''
		This function expects an eulfedora object, then exports entire object as WSUDOR objectBag.
		We will want to return a Bag object, complete with the manifest information.
		We will probably want to use bagit.make_bag, perhaps with the result of this file?
		Yes.  Export to directory, THEN make bag of that.  If all goes as planned, the
		checksums should match the original checksums.  

		Validating that would be possible.		
		'''

		# create temp dir
		temp_dir = "/tmp/Ouroboros/bagging_area/{pid_suffix}".format(pid_suffix=self.pid_suffix)		
		os.system("mkdir {temp_dir}".format(temp_dir=temp_dir))

		# export MODS
		fhand = open("{temp_dir}/MODS.xml".format(temp_dir=temp_dir), "w")
		MODS_handle = self.ohandle.getDatastreamObject("MODS")
		fhand.write(MODS_handle.content.serialize())
		fhand.close()

		# export RELS-EXT
		fhand = open("{temp_dir}/RELS-EXT.xml".format(temp_dir=temp_dir), "w")
		RELS_handle = self.ohandle.getDatastreamObject("RELS-EXT")
		fhand.write(RELS_handle.content.serialize())
		fhand.close()

		# export POLICY
		fhand = open("{temp_dir}/POLICY.xml".format(temp_dir=temp_dir), "w")
		POLICY_handle = self.ohandle.getDatastreamObject("POLICY")
		fhand.write(RELS_handle.content.serialize())
		fhand.close()

		# for datastream in remaining datastreams, export to /datastreams directory		
		os.system("mkdir {temp_dir}/datastreams".format(temp_dir=temp_dir))

		for DS in self.ohandle.ds_list:
			
			if DS in ['MODS','RELS-EXT','POLICY']:
				continue

			DS_handle = self.ohandle.getDatastreamObject(DS)

			print "Mime type: {mimetype}. Guessed file extension: {guess}".format(mimetype=DS_handle.mimetype,guess=mimetypes.guess_extension(DS_handle.mimetype))

			fhand = open("{temp_dir}/datastreams/{DS_ID}{extension_guess}".format(temp_dir=temp_dir,DS_ID=DS_handle.id, extension_guess=mimetypes.guess_extension(DS_handle.mimetype)), "wb")
			if DS_handle.control_group == "M":			
				fhand.write(DS_handle.content)
			if DS_handle.control_group == "X":			
				fhand.write(DS_handle.content.serialize())
			fhand.close()


		# finally, create bag
		bag = bagit.make_bag(temp_dir, {'Contact-Name': 'Graham Hukill'})

		return "The results of {PID} objectBag exporting...".format(PID=self.pid)



	# ignest parent script, will run sub-ingest scripts based on content_model
	def ingestBag(self):
		print "Bag content_type reads:",self.objMeta['content_model']

		# Image
		if self.objMeta['content_model'] == "Image":
			ingest_result = self.ingestImage()

		
		# finis
		print ingest_result

	# ingest image type
	def ingestImage(self):
		'''
		Can this itself fire a job?
		Like, 3/10 stages complete, etc.
		'''
		# DEBUG
		try:
			fedora_handle.purge_object('wayne:BAGTESTtree1')
			print "object purged"
		except:
			print "did not find"

		# create object
		ohandle = fedora_handle.get_object(self.objMeta['id'], create=True)
		ohandle.label = self.objMeta['label']
		# commit it, requisite for writing datastreams below
		ohandle.save()

		# write POLICY datastream
		# NOTE: 'E' management type required, not 'R'
		print "Using policy:",self.objMeta['policy']
		policy_suffix = self.objMeta['policy'].split("info:fedora/")[1]
		policy_handle = eulfedora.models.DatastreamObject(ohandle,"POLICY", "POLICY", mimetype="text/xml", control_group="E")
		policy_handle.ds_location = "http://localhost/fedora/objects/{policy}/datastreams/POLICY_XML/content".format(policy=policy_suffix)
		policy_handle.label = "POLICY"
		policy_handle.save()

		# write objMeta as datastream
		objMeta_handle = eulfedora.models.FileDatastreamObject(ohandle, "OBJMETA", "Ingest Bag Object Metadata", mimetype="application/json", control_group='M')
		objMeta_handle.label = "Ingest Bag Object Metadata"
		objMeta_handle.content = json.dumps(self.objMeta)
		objMeta_handle.save()

		# write RELS-EXT relationships
		for pred_key in self.objMeta['object_relationships'].keys():
			ohandle.add_relationship(pred_key,self.objMeta['object_relationships'][pred_key])

		# create derivatives and write datastreams
		for ds in self.objMeta['datastreams']:
			file_path = self.Bag.path + "/data/datastreams/" + ds['filename']
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
			thumb_handle = eulfedora.models.FileDatastreamObject(ohandle, "{ds_id}_THUMBNAIL".format(ds_id=ds['ds_id']), ds['label'], mimetype=ds['mimetype'], control_group='M')
			thumb_handle.label = ds['label']
			thumb_handle.content = open(temp_filename)
			thumb_handle.save()
			os.system('rm {temp_filename}'.format(temp_filename=temp_filename))

			# make preview

			# make jp2

		# write RELS-INT



		# finally, save and commit object
		return ohandle.save()









