# Mellon Books bag class

import uuid, json, os
import bagit
from inc import WSUDOR_bagger
from lxml import etree
from sets import Set
from WSUDOR_Manager import logging, db, models

'''
Assumptions:
1) Abbyy has generated tif, htm, and xml files
2) These files (along with a pdf and epub) are placed in folders that are named for each object DMDID
3) Each pdf file has been renamed to PDF_FULL.pdf
'''

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
			# make constituent_objects dir
			os.mkdir("/".join([self.obj_dir,"constituent_objects"]))


	def createBag(self, job_package=False):

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
		# Aggregate binaries as page dictionaries
		########################################################################################################################
		'''
		Create separate bags for each page
		Expecting image, html, and altoxml for each page
		'''

		# aggregate pages before making bags
		pages = {}

		# set page_num_bump
		page_num_bump = 0

		# gather files from source directory and sort
		binary_files = [ binary for binary in os.listdir(d) ]
		binary_files.sort() #sort

		for ebook_binary in binary_files:

			# skip some undesirables
			if ebook_binary == ".DS_Store" \
			or ebook_binary.endswith('bak') \
			or ebook_binary == "Thumbs.db" \
			or ebook_binary.endswith('png') \
			or ebook_binary.startswith('._') \
			or ebook_binary.endswith('txt'):
				continue

			# get mimetype and future ds_id of file
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
				'txt': ('text/plain','TEXT'),
				'epub': ('application/epub+zip', 'EPUB')
			}
			filetype_tuple = filetype_hash[ebook_binary.split(".")[-1]]
			# determine page num and DS ID
			page_num = ebook_binary.split(".")[1].lstrip('0')
			if page_num == '':
				page_num_bump = 1
				page_num = '0'
			try:
				page_num = int(page_num) + int(page_num_bump)

				# push to image num list
				if filetype_tuple[1] == 'IMAGE':
					page_num_list.append(page_num)

				# add to pages dictionary
				if page_num not in pages.keys():

					# write to constituent_objects list		
					page_dict = {
						'pid':"%s_Page_%s" % (self.pid, page_num),
						'directory':"wayne-%s_Page_%s" % (self.full_identifier, page_num),					
						'order':page_num,
						'datastreams':[]
					}

				pages[page_num] = page_dict

				# add to page entry
				pages[page_num]['datastreams'].append((ebook_binary,filetype_tuple[0],filetype_tuple[1]))

				# DEBUG
				logging.debug(pages)

			except:
				# add datastream
				# write to datastreams list
				if filetype_tuple[1] == "EPUB":
					ds_id = filetype_tuple[1]
					order = 1
				if filetype_tuple[1] == "PDF":
					ds_id = ebook_binary.split(".")[0]
					order = 2

				ds_dict = {
					"filename":ebook_binary,
					"ds_id":ds_id,
					"mimetype":filetype_tuple[0], # generate dynamically based on file extension
					"label":filetype_tuple[1],
					"internal_relationships":{},
					'order':order
				}
				self.objMeta_handle.datastreams.append(ds_dict)
		


		########################################################################################################################
		# Create page bags in SELF/constituent_objects
		########################################################################################################################

		# create constituent object ObjMeta
		for page_num in pages.keys():

			# get page dict
			page_dict = pages[page_num]
			logging.debug("writing ObjMeta for page %s" % page_num)
			logging.debug(page_dict)

			# generate page_obj_dir
			page_obj_dir = "/".join( [self.obj_dir, 'constituent_objects', page_dict['pid'].replace(":","-")] )
			if not os.path.exists(page_obj_dir):
				# make root dir
				os.mkdir(page_obj_dir)
				# make data dir
				os.mkdir("/".join([page_obj_dir,"datastreams"]))

			# instantiate object with quick variables
			book_title_short = (book_title[:100] + '..') if len(book_title) > 100 else book_title
			objMeta_primer = {
				"id":page_dict['pid'],
				"identifier":page_dict['pid'].split(":")[-1],
				"label":"%s - Page %s" % (book_title_short,page_num),
				"content_type":'WSUDOR_WSUebook_Page',
				"directory":page_dict['pid'].replace(":","-"),
				"order":page_num
			}

			# instantiate ObjMeta object
			page_objMeta_handle = self.ObjMeta(**objMeta_primer)
			
			# isRepresentedBy
			page_objMeta_handle.isRepresentedBy = "IMAGE"

			# write known relationships
			page_objMeta_handle.object_relationships = [				
				{
					"predicate": "http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/isDiscoverable",
					"object": "info:fedora/False"
				},
				{
					"predicate": "http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/preferredContentModel",
					"object": "info:fedora/CM:WSUebook_Page"
				},
				{
					"predicate": "http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/hasSecurityPolicy",
					"object": "info:fedora/wayne:WSUDORSecurity-permit-apia-unrestricted"
				},
				{
					"predicate": "http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/pageOrder",
					"object": str(page_num)
				},
				{
					"predicate": "info:fedora/fedora-system:def/relations-external#isConstituentOf",
					"object": "info:fedora/%s" % self.pid
				}
			]

			# write datastreams from page_dict
			for datastream in page_dict['datastreams']:
				logging.debug("working on datastream: %s" % str(datastream))
				
				# write symlink
				source = "/".join([ d, datastream[0] ])
				symlink = "/".join([ page_obj_dir, "datastreams", datastream[0] ])
				os.symlink(source, symlink)

				# add datastream
				# write to datastreams list		
				ds_dict = {
					"filename":datastream[0],
					"ds_id":datastream[2],
					"mimetype":datastream[1], # generate dynamically based on file extension
					"label":datastream[2],
					"internal_relationships":{},
					'order':page_num
				}
				page_objMeta_handle.datastreams.append(ds_dict)

			logging.debug("Page ObjMeta %s" % page_objMeta_handle.toJSON())

			# add to page objMeta to book's constituent_objects
			self.objMeta_handle.constituent_objects.append(page_objMeta_handle.asDict())

			# write to objMeta.json file 
			page_objMeta_handle.writeToFile("%s/objMeta.json" % (page_obj_dir))
			
			# use WSUDOR bagger (NO MD5 CHECKSUMS)
			bag = WSUDOR_bagger.make_bag(page_obj_dir, {
				'Object PID' : page_dict['pid']
			})


		# set isRepresentedBy relationship
		'''
		Sort list of page numbers, use lowest.
		Then, create single datastream for this object
		'''		
		page_num_list.sort()
		logging.debug("book is represented by page num %s" % page_num_list[0])
		self.objMeta_handle.isRepresentedBy = "%s_Page_%s" % (self.pid, page_num_list[0])

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

		# create symlinks for any binaries that don't fit into pages/constituent objects

			for datastream in self.objMeta_handle.datastreams:
				logging.debug("working on datastream: %s" % str(datastream['filename']))
				
				# write symlink
				source = "/".join([ d, datastream['filename'] ])
				symlink = "/".join([ self.obj_dir, "datastreams", datastream['filename'] ])
				os.symlink(source, symlink)


		# write to objMeta.json file 
		self.objMeta_handle.writeToFile("%s/objMeta.json" % (self.obj_dir))
		
		# use WSUDOR bagger (NO MD5 CHECKSUMS)
		bag = WSUDOR_bagger.make_bag(self.obj_dir, {
			'Collection PID' : "wayne:collectionWSUebooks",
			'Object PID' : self.pid
		})

		# because ingestWorkspace() picks up from here, simply return bag location
		return self.obj_dir







