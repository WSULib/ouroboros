# ebook v2 to v3 conversion

# python
import os
import json
import StringIO
import requests

from WSUDOR_Manager import *

from WSUDOR_Manager import fedoraHandles
fedora_handle = fedoraHandles.fedora_handle

# shorthand
w = WSUDOR_ContentTypes.WSUDOR_Object

import eulfedora


def ebook_v3_conversion(pid):

	# open book
	obj = w(pid)

	# use manifest for navigating pages
	im = obj.iiif_manifest
	if not im:
		im = json.loads(obj.genIIIFManifest())
	pages = obj.iiif_manifest['sequences'][0]['canvases']

	# create book object (consider wrapping in try / except for rollover here)
	result = createBookObj(obj)

	# create page objects
	for page in pages:
		createPageObj(obj,page)


def createBookObj(obj):

	ds_migrate = [
		'POLICY',
		'OBJMETA',
		'MODS',
		'DC',
		'THUMBNAIL',
		'HTML_FULL',
		'PDF_FULL',
		'BAGIT_META',
		'RELS-EXT',
		'RELS-INT'
	]

	# temporary pid
	tpid = "wayne:_%s" % obj.pid.split(":")[1]
	print "temp pid:",tpid

	# creating temp obj	
	tobj = fedora_handle.get_object(tpid)
	if tobj.exists:
		fedora_handle.purge_object(tobj)	
	tobj = fedora_handle.get_object(tpid, create=True)
	tobj.save()

	# label
	tobj.label = obj.ohandle.label

	# migrate datastreams
	for ds in ds_migrate:

		print "working on",ds

		# open source ds
		sds = obj.ohandle.getDatastreamObject(ds)

		# write objMeta as datastream
		nds = eulfedora.models.FileDatastreamObject(tobj, sds.id, sds.label, mimetype=sds.mimetype, control_group=sds.control_group)
		nds.label = sds.label

		# XML ds
		if type(sds) == eulfedora.models.XmlDatastreamObject:
			print "retrieving XML type content"
			nds.ds_location = "http://localhost/fedora/objects/%s/datastreams/%s/content" % (obj.pid, ds)

		# RDF ds
		if type(sds) == eulfedora.models.RdfDatastreamObject:
			print "retrieving RDF type content"
			rdf_content = requests.get("http://localhost/fedora/objects/%s/datastreams/%s/content" % (obj.pid, ds)).content
			rdf_content_scrubbed = rdf_content.replace(obj.pid, tpid)

			# write to file on disk
			filename = '/tmp/Ouroboros/%s_%s.rdf' % (tobj.pid, ds)
			with open(filename,'w') as fhand:
				fhand.write(rdf_content_scrubbed)

			# open as file object
			nds.content = open(filename)

		# Generic ds
		else:
			print "writing generic type content"
			nds.content = sds.content

		# saving datastream
		print "saving datastream %s" % ds
		nds.save()

		# cleanup
		if 'filename' in locals() and os.path.exists(filename):
			print "removing temporary XML file",filename
			os.remove(filename)


	# save new object
	print "saving temp book object"
	tobj.save()



def createPageObj(obj, page):
	pass

def rollback():
	pass











