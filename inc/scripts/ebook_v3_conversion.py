# ebook v2 to v3 conversion

# python
import os
import json
import StringIO
import requests
import time
import re
import datetime

from WSUDOR_Manager import *

from WSUDOR_Manager import fedoraHandles
fedora_handle = fedoraHandles.fedora_handle

# shorthand
w = WSUDOR_ContentTypes.WSUDOR_Object

import eulfedora


def ebook_v3_conversion(pid):

	stime = time.time()

	# open book
	wobj = w(pid)

	# create book object (consider wrapping in try / except for rollover here)
	try:
		tobj = createBookObj(wobj)
	except:
		print "Failed to create book object - rolling back and aborting"
		rollback(pid, 'book')

	# create page objects
	try:
		for k in wobj.pages_from_objMeta:
			createPageObj(wobj, k, wobj.pages_from_objMeta[k])		
	except:
		print "Failed to create page objects - rolling back and aborting"
		rollback(pid, 'pages')

	# purge original object, and create new
	try:
		replaceSourceObj(wobj, tobj)
	except:
		print "Failed to replace source book - rolling back and aborting"
		rollback(pid, 'replace')

	# report
	etime = time.time()
	ttime = float(etime - stime)
	print "Finished %s in %f seconds" % (pid,ttime)


def createBookObj(wobj):

	ds_migrate = [
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
	tpid = "wayne:_%s" % wobj.pid.split(":")[1]

	print "------------> working on %s" % tpid

	# creating temp tobj	
	tobj = fedora_handle.get_object(tpid)
	if tobj.exists:
		fedora_handle.purge_object(tobj)	
	tobj = fedora_handle.get_object(tpid, create=True)
	tobj.save()

	# label
	tobj.label = wobj.ohandle.label

	# write POLICY datastream
	# NOTE: 'E' management type required, not 'R'
	print "Using policy:",wobj.objMeta['policy']
	policy_suffix = wobj.objMeta['policy'].split("info:fedora/")[1]
	policy_handle = eulfedora.models.DatastreamObject(tobj, "POLICY", "POLICY", mimetype="text/xml", control_group="E")
	policy_handle.ds_location = "http://localhost/fedora/objects/%s/datastreams/POLICY_XML/content" % (policy_suffix)
	policy_handle.label = "POLICY"
	policy_handle.save()

	# migrate datastreams
	for ds in ds_migrate:

		print "---> working on",ds

		# open source ds
		sds = wobj.ohandle.getDatastreamObject(ds)

		# write objMeta as datastream
		nds = eulfedora.models.FileDatastreamObject(tobj, sds.id, sds.label, mimetype=sds.mimetype, control_group=sds.control_group)
		nds.label = sds.label

		# XML ds
		if type(sds) == eulfedora.models.XmlDatastreamObject:
			print "retrieving XML type content"
			nds.ds_location = "http://localhost/fedora/objects/%s/datastreams/%s/content" % (wobj.pid, ds)

		# RDF ds
		if type(sds) == eulfedora.models.RdfDatastreamObject:
			print "retrieving RDF type content"
			rdf_content = requests.get("http://localhost/fedora/objects/%s/datastreams/%s/content" % (wobj.pid, ds)).content
			rdf_content_scrubbed = rdf_content.replace(wobj.pid, tpid)

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

	return tobj



def createPageObj(wobj, page_num, page_dict):

	# # DEBUG
	# if page_num > 5:
	# 	return False

	print "------------> working on page %s" % page_num

	# new pid
	npid = "wayne:%s_Page_%s" % (wobj.pid.split(":")[1], page_num)

	# creating new nobj	
	nobj = fedora_handle.get_object(npid)
	if nobj.exists:
		fedora_handle.purge_object(nobj)	
	nobj = fedora_handle.get_object(npid, create=True)
	nobj.save()

	# label
	nobj.label = "%s - Page %s" % (wobj.ohandle.label, page_num)

	# write POLICY datastream
	# NOTE: 'E' management type required, not 'R'
	print "Using policy:",wobj.objMeta['policy']
	policy_suffix = wobj.objMeta['policy'].split("info:fedora/")[1]
	policy_handle = eulfedora.models.DatastreamObject(nobj, "POLICY", "POLICY", mimetype="text/xml", control_group="E")
	policy_handle.ds_location = "http://localhost/fedora/objects/%s/datastreams/POLICY_XML/content" % (policy_suffix)
	policy_handle.label = "POLICY"
	policy_handle.save()

	# generic datastreams
	generic_ds = [
		"IMAGE",
		"JP2",
		"THUMBNAIL",
		"HTML",
		"ALTOXML",
	]

	# generic hash of target ids
	target_ids = {
		'IMAGE':'IMAGE_%d' % page_num,
		'JP2':'IMAGE_%d_JP2' % page_num,
		'THUMBNAIL':'IMAGE_%d_THUMBNAIL' % page_num,
		'HTML':'HTML_%d' % page_num,
		'ALTOXML':'ALTOXML_%d' % page_num
	}

	# write datastreams from objMeta
	for ds in generic_ds:

		# open source datastream
		sds = wobj.ohandle.getDatastreamObject(target_ids[ds])

		print "---> working on", sds.label

		# write objMeta as datastream
		nds = eulfedora.models.FileDatastreamObject(nobj, ds, ds, mimetype=sds.mimetype, control_group='M')
		nds.label = ds
		nds.ds_location = "http://localhost/fedora/objects/%s/datastreams/%s/content" % (wobj.pid, sds.id )
		nds.save()

	# write RDF relationships
	nobj.add_relationship("info:fedora/fedora-system:def/relations-external#hasContentModel", "info:fedora/CM:WSUebook_Page")
	nobj.add_relationship("info:fedora/fedora-system:def/relations-external#isConstituentOf", "info:fedora/%s" % wobj.pid)
	nobj.add_relationship("http://digital.library.wayne.edu/fedora/objects/wayne:WSUDOR-Fedora-Relations/datastreams/RELATIONS/content/pageOrder", page_num)

	# save page object
	return nobj.save()


# shuffle book objects
def replaceSourceObj(wobj, tobj):

	# export old book object with airlock
	os.system('python /opt/eulfedora/scripts/repo-cp --config /home/ouroboros/.repocpcfg --export-format archive --omit-checksums local /tmp/Ouroboros/airlock_hold %s' % (wobj.pid))

	# export new book object with airlock
	os.system('python /opt/eulfedora/scripts/repo-cp --config /home/ouroboros/.repocpcfg --export-format archive --omit-checksums local /tmp/Ouroboros/airlock %s' % (tobj.pid))

	# write FOXML, replace PID, omit checksums
	FOXML_filename = '/tmp/Ouroboros/airlock/%s.xml' % tobj.pid
	with open(FOXML_filename ,'r') as fhand:
		FOXML = fhand.read()
		FOXML = FOXML.replace(tobj.pid, wobj.pid)
		FOXML = re.sub(r'<foxml:contentDigest.+?/>', '', FOXML)
	with open(FOXML_filename ,'w') as fhand:
		fhand.write(FOXML)

	# purge old object
	print "purging old book object..."
	fedora_handle.purge_object(wobj.pid)

	# ingest new object
	print "ingesting new book object..."
	# import new book object with airlock
	os.system('python /opt/eulfedora/scripts/repo-cp --config /home/ouroboros/.repocpcfg --export-format archive --omit-checksums /tmp/Ouroboros/airlock local')

	# index new object
	nwobj = w(wobj.pid)
	nwobj.indexToSolr()

	# purge temporary object
	print "purging temporary book object"
	fedora_handle.purge_object(tobj.pid)

	# cleanup
	print "cleaning up..."
	if os.path.exists(FOXML_filename):
		print "removing",FOXML_filename
		os.remove(FOXML_filename)

	return nwobj
	


def rollback(pid, rollback_type):

	print "rolled back v3 conversion for %s, writing to log" % pid
	with open('/tmp/Ouroboros/ebook_v3_conversion.log','a') as fhand:
		fhand.write("\n%s - %s failed at %s" % (datetime.datetime.now().strftime('%Y-%m-%d-%H:%M:%S'), pid, rollback_type))
	
	# book failed, rollback and return
	if rollback_type == 'book':
		print "rolling back from bad book ingest"
		# delete temp book
		tpid = "wayne:_%s" % pid.split(":")[1]
		try:
			fedora_handle.purge_object(tpid)
			print "temp book found, purged"
		except:
			print "temp book not found, skipping rollback purge"
		
		# finally, return
		return False

	# pages failed, rollback, then run book rollback
	if rollback_type == 'pages':
		print "rolling back from bad pages ingest"

		# find page objects
		pages = fedora_handle.find_objects("%s_Page_*" % pid)
		for page in pages:
			fedora_handle.purge_object(page)

		# recurse to run book
		rollback(pid, 'book')

	# fail near end, roll back all
	if rollback_type == 'replace':
		print "rolling back from bad source replace ingest"

		# rollback pages (which calls book)
		rollback(pid, 'pages')












