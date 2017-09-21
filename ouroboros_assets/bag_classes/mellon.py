# Mellon book ingestion

'''
Before you run this class, please note the below instructions:
Class expects datastreams (epub, pdf) to be placed in folders that match the object DMDID
Also, expects a cover image called COVER_IMAGE in the same folder
'''


import uuid, json, os
import mimetypes
import bagit
from lxml import etree
from WSUDOR_Manager import logging


# define required `BagClass` class
class BagClass(object):
	
		
	# class is expecting a healthy amount of input from `ingestWorkspace` script, and object row
	def __init__(self, object_row, ObjMeta, bag_root_dir, files_location, purge_bags):

		# hardcoded
		self.name = 'mellon'  # human readable name, ideally matching filename, for this bag creating class
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

		# derived
		# MODS_handle (parsed with etree)
		try:
			MODS_tree = etree.fromstring(self.MODS)
			MODS_root = MODS_handle.getroot()
			ns = MODS_root.nsmap
			MODS_handle = MODS_root.xpath('//mods:mods', namespaces=ns)[0]
		except:
			logging.debug("could not parse MODS from DB string")

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
		logging.debug("%s" % self.full_identifier)

		# generate PID
		self.pid = "wayne:%s" % (self.full_identifier)

		# write MODS
		with open("%s/MODS.xml" % (self.obj_dir), "w") as fhand:
			fhand.write(self.MODS)		
	
		# instantiate object with quick variables
		objMeta_primer = {
			"id":"wayne:"+self.full_identifier,
			"identifier":self.full_identifier,
			"label":self.object_title,
			"content_type":self.content_type
		}

		# instantiate ObjMeta object
		self.objMeta_handle = self.ObjMeta(**objMeta_primer)



		################################################################
		# set Cover Image

		# set binary files location
		d = "/".join([self.files_location, self.full_identifier])
		logging.debug("full path is %s" % d)

		
		# Identify datastreams folder
		datastreams_dir = self.obj_dir + "/datastreams"

		# collection art file
		logging.debug("Looking in: %s" % d)
		
		# find cover image
		m_files = [ binary for binary in os.listdir(d) if binary.startswith('COVER_IMAGE') ]

		if len(m_files) == 1:

			logging.debug("%s" % m_files[0])
			
			filename = m_files[0]

			label = "Cover Image"
			order = 1

			# get extension, ds_id
			mimetypes.init()
			ds_id, ext = os.path.splitext(filename)

			# create datastream dictionary
			ds_dict = {
				"filename": filename,
				"ds_id": 'COVER_IMAGE',
				"mimetype": mimetypes.types_map[ext],
				"label": label,
				"internal_relationships": {},
				'order': order
			}

			self.objMeta_handle.datastreams.append(ds_dict)

			# make symlinks to datastreams on disk
			bag_location = datastreams_dir + "/" + filename

			# determine remote_location by parsing filename
			source = "/".join([ d, filename ])
			os.symlink(source, bag_location)
			
			# set as representative datastream
			self.objMeta_handle.isRepresentedBy = 'COVER_IMAGE'
		
		else:
			logging.debug("Could not locate Cover Image, skipping.")
		

		################################################################	


		################################################################
		# Get (non-cover image) datastreams

		# iterate through SORTED binaries and create symlinks and write to objMeta		
		logging.debug("creating symlinks and writing to objMeta")
		logging.debug("looking in %s" % self.files_location)

		# get binary_files location
		binary_files = [ binary for binary in os.listdir(d) if not binary.startswith('COVER_IMAGE') ]
		binary_files.sort() #sort
		num = 0
		for ebook_binary in binary_files:

			# skip some undesirables
			if ebook_binary == ".DS_Store" or ebook_binary.endswith('bak') or ebook_binary == "Thumbs.db" or ebook_binary.endswith('png') or ebook_binary.startswith('._'):
				continue

			# write symlink
			source = "/".join([ d, ebook_binary ])
			symlink = "/".join([ self.obj_dir, "datastreams", ebook_binary ])
			os.symlink(source, symlink)		

			ds_id = ebook_binary.split(".")[0]

			# get mimetype of file
			filetype_hash = {
				'tiff': ('image/tiff','IMAGE'),
				'tif': ('image/tiff','IMAGE'),
				'jpg': ('image/jpeg','IMAGE'),
				'jpeg': ('image/jpeg','IMAGE'),
				'png': ('image/png','IMAGE'),
				'xml': ('text/xml','ALTOXML'),
				'html': ('text/html','HTML'),
				'htm': ('text/html','HTML'),
				'pdf': ('application/pdf','PDF'),
				'epub': ('application/epub+zip', 'EPUB')
			}
			filetype_tuple = filetype_hash[ebook_binary.split(".")[-1]]

			# write to datastreams list		
			ds_dict = {
				"filename":ebook_binary,
				"ds_id":ds_id,
				"mimetype":filetype_tuple[0], # generate dynamically based on file extension
				"label":ds_id,
				"internal_relationships":{},
				'order':num+2 # cover image ds is first in order, so starting at 2 for the subsequent datastreams
			}
			self.objMeta_handle.datastreams.append(ds_dict)
			num = num + 1

		################################################################	

		# write known relationships
		self.objMeta_handle.object_relationships = [				
			{
				"predicate": "info:fedora/fedora-system:def/relations-external#isMemberOfCollection",
				"object": "info:fedora/wayne:collection%s" % (self.collection_identifier)
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

		# write to objMeta.json file 
		self.objMeta_handle.writeToFile("%s/objMeta.json" % (self.obj_dir))

		# make bag
		bag = bagit.make_bag(self.obj_dir, {
			'Collection PID' : "wayne:collection"+self.collection_identifier,
			'Object PID' : self.pid
		}, processes=1)


		return self.obj_dir
