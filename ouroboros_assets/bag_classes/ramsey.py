# DSJ bag class

import uuid, json, os
import bagit
from inc import WSUDOR_bagger
from lxml import etree
from sets import Set
from WSUDOR_Manager import logging

'''
This can be rewritten, with some instructions for making the books on disk.  
	- find root folder, assume ###.* book files there
	- can clean up page number grabbing, where all end up starting with 1
'''

# define required `BagClass` class
class BagClass(object):
	
		
	# class is expecting a healthy amount of input from `ingestWorkspace` script, and object row
	def __init__(self, object_row, ObjMeta, bag_root_dir, files_location, purge_bags):

		# hardcoded
		self.name = 'ramsey'  # human readable name, ideally matching filename, for this bag creating class
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
		print self.full_identifier

		# generate PID
		self.pid = "wayne:%s" % (self.full_identifier)

		# write MODS
		with open("%s/MODS.xml" % (self.obj_dir), "w") as fhand:
			fhand.write(self.MODS)


		# construct
		################################################################
		
		# get identifier
		identifier = self.MODS_handle['MODS_element'].xpath('//mods:identifier[@type="local"]', namespaces=self.MODS_handle['MODS_ns'])[0].text
		logging.debug("identifier: %s" % identifier)

		# get title
		book_title = self.MODS_handle['MODS_element'].xpath('mods:titleInfo/mods:title',namespaces=self.MODS_handle['MODS_ns'])[0].text
		logging.debug("full title: %s" % book_title)

		# instantiate object with quick variables
		objMeta_primer = {
			"id":"wayne:%s" % identifier,
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

		# get binary_files location
		sm = json.loads(self.object_row.struct_map)
		file_part = sm['mets:div']['mets:fptr']['@FILEID']
		logging.debug("file part is %s" % file_part)
		d = "/".join([self.files_location, file_part, "etext_files_%s" % file_part])
		logging.debug("full path is %s" % d)

		binary_files = [ binary for binary in os.listdir(d) ]
		binary_files.sort() #sort
		for ebook_binary in binary_files:

			# skip some undesirables
			if ebook_binary == ".DS_Store" or ebook_binary.endswith('bak') or ebook_binary == "Thumbs.db" or ebook_binary.endswith('png') or ebook_binary.startswith('._'):
				continue

			# write symlink
			source = "/".join([ d, ebook_binary ])
			symlink = "/".join([ self.obj_dir, "datastreams", ebook_binary ])
			os.symlink(source, symlink)		

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
				'pdf': ('application/pdf','PDF')
			}
			filetype_tuple = filetype_hash[ebook_binary.split(".")[-1]]

			'''
			Because the image and etext files come with such sporadic numbering,
			it's difficult to just extract the page number that way.  

			It might be better to just sort and begin numbering from 1.
			'''
			
			# determine page num and DS ID
			page_num = ebook_binary.split(".")[0].lstrip('0')
			if page_num == '':
				page_num = '1'

			ds_id = filetype_tuple[1]+"_"+page_num

			# push to image num list
			if filetype_tuple[1] == 'IMAGE':
				page_num_list.append((int(page_num), ds_id))

			# write to datastreams list		
			ds_dict = {
				"filename":ebook_binary,
				"ds_id":ds_id,
				"mimetype":filetype_tuple[0], # generate dynamically based on file extension
				"label":ds_id,
				"internal_relationships":{},
				'order':page_num			
			}
			self.objMeta_handle.datastreams.append(ds_dict)

		# set isRepresentedBy relationsihp
		'''
		Sort list of page numbers, use lowest.
		'''		
		# page_num_list.sort()
		# logging.debug("Setting is represented to page num %s, ds_id %s" % page_num_list[0])
		# self.objMeta_handle.isRepresentedBy = page_num_list[0][1]
		self.objMeta_handle.isRepresentedBy = "IMAGE_1"

		# write known relationships
		self.objMeta_handle.object_relationships = [				
			{
				"predicate": "info:fedora/fedora-system:def/relations-external#isMemberOfCollection",
				"object": "info:fedora/wayne:collectionWSUebooks"
			},
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
		# bag = bagit.make_bag(self.obj_dir, {
		# 	'Collection PID' : "wayne:collectionWSUebooks",
		# 	'Object PID' : self.pid
		# }, processes=1)
		
		# use WSUDOR bagger (NO MD5 CHECKSUMS)
		bag = WSUDOR_bagger.make_bag(self.obj_dir, {
			'Collection PID' : "wayne:collectionWSUebooks",
			'Object PID' : self.pid
		})

		# because ingestWorkspace() picks up from here, simply return bag location
		return self.obj_dir








