# Collection Object class

import uuid, json, os
import bagit
from lxml import etree
import mimetypes
from WSUDOR_Manager import logging


# define required `BagClass` class
class BagClass(object):
	
		
	# class is expecting a healthy amount of input from `ingestWorkspace` script, and object row
	def __init__(self, object_row, ObjMeta, bag_root_dir, files_location, purge_bags):
		print "object_row"
		print object_row
		print "ObjMeta"
		print ObjMeta
		print "bag_root_dir"
		print bag_root_dir
		print "files_location"
		print files_location
		print "purge_bags"
		print purge_bags
		# hardcoded
		self.name = 'Collection'  # human readable name, ideally matching filename, for this bag creating class
		self.content_type = 'WSUDOR_Collection'  # not required, but easy place to set the WSUDOR_ContentType

		# passed
		self.object_row = object_row  # handle for object mysql row in 'ingest_workspace_object'
		self.ObjMeta = ObjMeta  # ObjMeta class from ouroboros.models
		self.bag_root_dir = bag_root_dir  # path for depositing formed bags
		self.files_location = files_location  # location of files: they might be flat, nested, grouped, etc.
		
		# derived from object_row
		self.MODS = object_row.MODS  # MODS as XML string		
		self.struct_map = object_row.struct_map  # JSON representation of structMap section from METS file for this object
		self.object_title = (object_row.object_title[:100] + '..') if len(object_row.object_title) > 100 else object_row.object_title
		self.DMDID = object_row.DMDID  # object DMDID from METS, probabl identifier for file (but not required, might be in MODS)
		self.collection_identifier = object_row.job.collection_identifier  # collection signifier, likely suffix to 'wayne:collection[THIS]'
		
		self.purge_bags = purge_bags

		# future
		self.objMeta_handle = None

		# generate obj_dir
		self.obj_dir = "/".join( [bag_root_dir, str(uuid.uuid4())] ) # UUID based hash directory for bag
		if not os.path.exists(self.obj_dir):
			# make root dir
			os.mkdir(self.obj_dir)
			# make data dir
			os.mkdir("/".join([self.obj_dir,"datastreams"]))		



	def createBag(self):

		'''
		Function to create bag given inputs.  Most extensive and complex part of this class.
		'''

		# set identifier
		self.full_identifier = self.DMDID
		print self.full_identifier

		# generate PID
		self.pid = "wayne:collection%s" % (self.full_identifier)

		# write MODS
		with open("%s/MODS.xml" % (self.obj_dir), "w") as fhand:
			fhand.write(self.MODS)		
	
		# instantiate object with quick variables
		objMeta_primer = {
			"id":self.pid,
			"identifier":self.full_identifier,
			"label":self.object_title,
			"content_type":self.content_type
		}

		# Instantiate ObjMeta object
		self.objMeta_handle = self.ObjMeta(**objMeta_primer)

		################################################################
		# set Collection Art
		
		# Identify datastreams folder
		datastreams_dir = self.obj_dir + "/datastreams"

		# collection art file
		print "Looking in: %s" % self.files_location
		
		# get remote_location from 
		fd = json.loads(self.object_row.job.file_index) # loads from MySQL

		# find collection art
		art_files = [ (k,fd[k]) for k in fd.keys() if k.startswith('COLLECTIONART') ]

		if len(art_files) == 1:

			print art_files[0]
			
			filename, remote_location = art_files[0]

			label = "Collection Art"
			order = 1

			# get extension, ds_id
			mimetypes.init()
			ds_id, ext = os.path.splitext(filename)

			# create datastream dictionary
			ds_dict = {
				"filename": filename,
				"ds_id": 'COLLECTIONART',
				"mimetype": mimetypes.types_map[ext],
				"label": label,
				"internal_relationships": {},
				'order': order
			}

			self.objMeta_handle.datastreams.append(ds_dict)

			# make symlinks to datastreams on disk
			bag_location = datastreams_dir + "/" + filename

			# determine remote_location by parsing filename
			filename_parts = filename.split("_")
			os.symlink(remote_location, bag_location)
			
			# set as representative datastream
			self.objMeta_handle.isRepresentedBy = 'COLLECTIONART'
		
		else:
			print "Could not locate Collection Art, skipping."
		

		################################################################		

		# write known relationships
		self.objMeta_handle.object_relationships = [
			{
				"predicate": "http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isDiscoverable",
				"object": "info:fedora/True"
			},
			{
				"predicate": "http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/preferredContentModel",
				"object": "info:fedora/CM:%s" % (self.content_type.split("_")[1])
			},
			{
				"predicate": "http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/hasSecurityPolicy",
				"object": "info:fedora/wayne:WSUDORSecurity-permit-apia-unrestricted"
			}		
		]

		# write to objMeta.json file 
		self.objMeta_handle.writeToFile("%s/objMeta.json" % (self.obj_dir))

		# make bag
		bag = bagit.make_bag(self.obj_dir, {
			'Collection PID' : self.pid,
			'Object PID' : self.pid
		}, processes=1)


		return self.obj_dir








