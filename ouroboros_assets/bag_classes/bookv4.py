# DSJ bag class

import uuid, json, os
import bagit
from inc import WSUDOR_bagger
from lxml import etree
from sets import Set
from WSUDOR_Manager import logging

'''
Assuming self.file_location is directory of loose files from Abbyy
'''

# define required `BagClass` class
class BagClass(object):
	
		
	# class is expecting a healthy amount of input from `ingestWorkspace` script, and object row
	def __init__(self, object_row, ObjMeta, bag_root_dir, files_location, purge_bags):

		# hardcoded
		self.name = 'generic_single'  # human readable name, ideally matching filename, for this bag creating class
		self.content_type = 'WSUDOR_WSUebook'  # not required, but easy place to set the WSUDOR_ContentType

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

		# MODS_handle (parsed with etree)
		MODS_root = etree.fromstring(self.MODS)	
		ns = MODS_root.nsmap
		self.MODS_handle = {
			"MODS_element" : MODS_root.xpath('//mods:mods', namespaces=ns)[0],
			"MODS_ns" : ns
		}

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

		# list of page nums and datastream filenames tuples
		page_num_list = []

		# set identifier
		self.full_identifier = self.DMDID
		logging.debug("%s" % self.full_identifier)

		# generate PID
		self.pid = "wayne:%s" % (self.full_identifier)
		self.object_row.pid = self.pid

		# write MODS
		with open("%s/MODS.xml" % (self.obj_dir), "w") as fhand:
			fhand.write(self.MODS)

		# get identifier
		try:
			identifier = self.MODS_handle['MODS_element'].xpath('//mods:identifier[@type="local"]', namespaces=self.MODS_handle['MODS_ns'])[0].text
			logging.debug("identifier: %s" % identifier)
		except:
			# fall back on self.full_identifier
			identifier = self.full_identifier

		# get title
		book_title = self.MODS_handle['MODS_element'].xpath('mods:titleInfo/mods:title',namespaces=self.MODS_handle['MODS_ns'])[0].text
		logging.debug("full title: %s" % book_title)

		# instantiate object with quick variables
		objMeta_primer = {
			"id":self.pid,
			"identifier":identifier,
			"label":book_title,
			"content_type":self.content_type,
			"image_filetype":"tif"
		}

		# instantiate ObjMeta object
		self.objMeta_handle = self.ObjMeta(**objMeta_primer)

		# iterate through SORTED binaries and create symlinks and write to objMeta		
		logging.debug("creating symlinks and writing to objMeta")
		logging.debug("looking in %s" % self.files_location)

		# get binary_files location, based on pid
		if self.files_location.endswith('/'):
			d = self.files_location[:-1]
		else:
			d = self.files_location
		# tack on pid as directory
		d += "/" + self.full_identifier



		########################################################################################################################
		'''
		Create seperate bags for each page
		Expecting image, html, and altoxml for each page
		'''




		########################################################################################################################



		# set isRepresentedBy relationsihp
		'''
		Sort list of page numbers, use lowest.
		'''		
		page_num_list.sort()
		logging.debug("Setting is represented to page num %s, ds_id %s" % page_num_list[0])
		self.objMeta_handle.isRepresentedBy = page_num_list[0][1]

		# write known relationships
		self.objMeta_handle.object_relationships = [				
			{
				"predicate": "info:fedora/fedora-system:def/relations-external#isMemberOfCollection",
				"object": "info:fedora/wayne:collectionWSUebooks"
			},
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

		# if collection identifier is not "Undefined"
		if self.collection_identifier != "Undefined":
			self.objMeta_handle.object_relationships.append(
				{
					"predicate": "info:fedora/fedora-system:def/relations-external#isMemberOfCollection",
					"object": "info:fedora/wayne:collection%s" % (self.collection_identifier)
				}
			)

		# write to objMeta.json file 
		self.objMeta_handle.writeToFile("%s/objMeta.json" % (self.obj_dir))
		
		# use WSUDOR bagger (NO MD5 CHECKSUMS)
		bag = WSUDOR_bagger.make_bag(self.obj_dir, {
			'Collection PID' : "wayne:collectionWSUebooks",
			'Object PID' : self.pid
		})

		# because ingestWorkspace() picks up from here, simply return bag location
		return self.obj_dir








