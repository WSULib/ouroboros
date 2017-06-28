
import WSUDOR_ContentTypes
from WSUDOR_Manager import logging, models
logging = logging.getChild("ebookv3tov4")



def convert_v3tov4(v3book_pid, commit=False):
	
	'''
	This function will take a v3 book and rewrite the objMeta for v4 export/ingest

	1) For each page (constituent of book)
		- write v4 objMeta
		- add datastreams
			- BAGIT_META
			- MODS
			- PDF (?)
			- OBJMETA

	2) 

	'''

	# open object
	v3book = WSUDOR_ContentTypes.WSUDOR_Object(v3book_pid)

	# itererate through pages (constituents) and generate objMeta for first time
	for obj in v3book.constituents:

		# load as WSUDOR
		v3page = WSUDOR_ContentTypes.WSUDOR_Object(obj.pid)

		# intuit page number
		page_num = int(v3page.pid.split("_")[-1])
		logging.debug("page number is: %s" % page_num)

		# get info from original v3 objMeta
		v3_objMeta_entry = v3book.pages_from_objMeta[page_num]
		logging.debug("original v3_objMeta_entry: %s" % v3_objMeta_entry)

		# start objMeta primer
		book_title_short = (v3book.ohandle.label.strip()[:100] + '..') if len(v3book.ohandle.label.strip()) > 100 else v3book.ohandle.label.strip()
		objMeta_primer = {
			"id":v3page.pid,
			"identifier":v3page.pid.split(":")[-1],
			"label":"%s - Page %s" % (book_title_short, page_num),
			"content_type":'WSUDOR_WSUebook_Page',
			"directory":v3page.pid.replace(":","-"),
			"order":page_num
		}

		# instantiate ObjMeta object
		v3page_objMeta = models.ObjMeta(**objMeta_primer)

		# isRepresentedBy
		v3page_objMeta.isRepresentedBy = "IMAGE"

		# write known relationships
		v3page_objMeta.object_relationships = [				
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
				"object": "info:fedora/%s" % v3book.pid
			}
		]

		# write raw book datastreams to objMeta
		for ds in v3_objMeta_entry:
			ds_dict = {
				"filename":ds['filename'],
				"ds_id":ds['ds_id'].split("_")[0], # remove page number
				"mimetype":ds['mimetype'], # generate dynamically based on file extension
				"label":ds['ds_id'].split("_")[0],
				"internal_relationships":{},
				'order':ds['order']
			}
			v3page_objMeta.datastreams.append(ds_dict)

		# DEBUG
		logging.debug("Page ObjMeta %s" % vars(v3page_objMeta))

		# write objMeta as datastream
		if commit:
			objMeta_handle = eulfedora.models.FileDatastreamObject(v3page.ohandle, "OBJMETA", "Ingest Bag Object Metadata", mimetype="application/json", control_group='M')
			objMeta_handle.label = "Ingest Bag Object Metadata"
			objMeta_handle.content = v3page_objMeta.toJSON()
			objMeta_handle.save()

		# write generic MODS
		if commit:
			# write generic MODS datastream
			MODS_handle = eulfedora.models.FileDatastreamObject(v3page.ohandle, "MODS", "MODS descriptive metadata", mimetype="text/xml", control_group='M')
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
			''' % (v3page_objMeta['label'], v3page_objMeta['id'].split(":")[1], v3page_objMeta['id'])
			logging.debug("%s" % raw_MODS)
			MODS_handle.content = raw_MODS
			MODS_handle.save()

		# write fake BAGIT_META
		'''
		generate fake bagit information (this will be fixed later)

		bag-info.txt
			Bag-Software-Agent: WSUDOR_bagger
			Bagging-Date: 06-28-2017
			Payload-Oxum: 1675876828
			Object PID: wayne:fourthfolio
			Collection PID: wayne:collectionWSUebooks
		bagit.txt
			BagIt-Version: 0.97
			Tag-File-Character-Encoding: UTF-8
		manifest-md5.txt
			- empty
		tagmanifest-md5.txt
			- empty
		'''




# def export_v3tov4():

# 	'''
# 	Goal is to export v3 books in the structure that IngestWorkspace would create for a v4 book.

# 	Roughly:
# 	/wayne:foobar

# 		/ data
# 			- MODS.xml
# 			- objMeta.json
# 			- RELS-EXT.xml
# 			- RELS-INT.xml

# 			/ datastreams
# 				- HTML_FULL # no file extension
# 				- PDF_FULL.pdf

# 			/ constituent_objects

# 				/ wayne:foobar_Page 1
# 					/ data
# 						/ datastreams
# 							- 001.tif
# 							- 001.pdf
# 							- 001.htm
# 							- 001.xml
# 						- MODS.xml
# 						- objMeta.json
# 						- RELS-EXT.xml
# 						- RELS-INT.xml					
# 					- manifest-md5.txt
# 					- tagmanifest-md5.txt
# 					- bag-info.txt
# 					- bagit.txt

# 		- manifest-md5.txt
# 		- tagmanifest-md5.txt
# 		- bag-info.txt
# 		- bagit.txt

# 	'''

# 	logging.debug("exporting v3 book for v4 ingest - to be used in conjunction with ingest_v3tov4()")


# def ingest_v3tov4():
# 	logging.debug("ingesting v3 book as v4 model - to be used in conjunction with export_v3tov4()")v