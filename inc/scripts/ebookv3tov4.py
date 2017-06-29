
import WSUDOR_ContentTypes
from WSUDOR_Manager import logging, models
logging = logging.getChild("ebookv3tov4")
import eulfedora



def convert_v3tov4(v3book_pid, single_page_num=False, commit=True):
	
	'''
	This function will take a v3 book and rewrite the objMeta for v4 export/ingest

	1) For each page (constituent of book)
		- write v4 objMeta
		- add datastreams
			- BAGIT_META
			- MODS
			- PDF (?)
			- OBJMETA

	2) update OBJMETA for book
	'''

	# open object
	v3book = WSUDOR_ContentTypes.WSUDOR_Object(v3book_pid)

	if single_page_num:
		logging.debug("only working on one page, then exiting")
		page_v3tov4(v3book, "%s_Page_%s" % (v3book.pid, single_page_num), commit=commit)
		return True

	else:
		logging.debug("Converting all pages, then book object itself")
		
		# itererate through pages, save objMeta from each
		pages_objMeta = []
		for obj in v3book.constituents:
			page_objMeta = page_v3tov4(v3book, obj.pid, commit=commit)
			pages_objMeta.append(page_objMeta)

		# update objMeta for book
		book_title_short = (v3book.ohandle.label.strip()[:100] + '..') if len(v3book.ohandle.label.strip()) > 100 else v3book.ohandle.label.strip()

		# instantiate new ObjMeta object
		v3book_objMeta = models.ObjMeta(**v3book.objMeta)

		# clear datastreams
		v3book_objMeta.datastreams = []

		# add HTML_FULL and PDF_FULL to objMeta.datastreams
		v3book_objMeta.datastreams.append({
			'mimetype': "text/html",
			'label': "Full HTML for item",
			'ds_id': "HTML_FULL",
			'internal_relationships': { },
			'filename': "HTML_FULL.htm"
			}
		)
		v3book_objMeta.datastreams.append({
			'mimetype': "application/pdf",
			'internal_relationships': { },
			'ds_id': "PDF_FULL",
			'label': "PDF_PDF_FULL",
			'filename': "PDF_FULL.pdf"
			}
		)

		# add all pages to constituent_objects
		v3book_objMeta.constituent_objects = pages_objMeta

		# update isRepresentedBy
		is_rep_num = v3book_objMeta.isRepresentedBy.split("_")[-1]
		v3book_objMeta.isRepresentedBy = "%s_Page_%s" % (v3book.pid, is_rep_num)

		# update objMeta datastream
		objMeta_handle = eulfedora.models.FileDatastreamObject(v3book.ohandle, "OBJMETA", "Ingest Bag Object Metadata", mimetype="application/json", control_group='M')
		objMeta_handle.label = "Ingest Bag Object Metadata"
		objMeta_handle.content = v3book_objMeta.toJSON()
		objMeta_handle.save()

		logging.debug("finished for %s" % v3book_pid)


def page_v3tov4(v3book, pid, commit=False):

	# load as WSUDOR
	v3page = WSUDOR_ContentTypes.WSUDOR_Object(pid)

	# intuit page number
	page_num = int(v3page.pid.split("_")[-1])
	logging.debug("page number is: %s" % page_num)

	# get info from original v3 objMeta
	v3_objMeta_entry = v3book.pages_from_objMeta_v1[page_num]
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
	objMeta_handle = eulfedora.models.FileDatastreamObject(v3page.ohandle, "OBJMETA", "Ingest Bag Object Metadata", mimetype="application/json", control_group='M')
	objMeta_handle.label = "Ingest Bag Object Metadata"
	objMeta_handle.content = v3page_objMeta.toJSON()
	if commit:
		objMeta_handle.save()

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
	''' % (vars(v3page_objMeta)['label'], vars(v3page_objMeta)['id'].split(":")[1], vars(v3page_objMeta)['id'])
	MODS_handle.content = raw_MODS
	if commit:
		MODS_handle.save()

	# write fake BAGIT_META
	'''
	generate fake bagit information (this will be fixed later)

	note: using placeholder file in /inc/sciprts/PLACEHOLDER_BAGIT_META

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
	# pull in BagIt metadata as BAG_META datastream tarball
	bag_meta_handle = eulfedora.models.FileDatastreamObject(v3page.ohandle, "BAGIT_META", "BagIt Metadata Tarball", mimetype="application/x-tar", control_group='M')
	bag_meta_handle.label = "BagIt Metadata Tarball"
	bag_meta_handle.content = open("inc/scripts/PLACEHOLDER_BAGIT_META")
	if commit:
		bag_meta_handle.save()

	# finish and return objMeta
	logging.debug("%s finished." % v3page.pid)
	return vars(v3page_objMeta)



