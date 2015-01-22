from WSUDOR_Manager import *
import os
import mimetypes
import json
import uuid
import Image
import time
import traceback
import sys
import cStringIO

import eulfedora

fedora_handle = fedoraHandles.fedora_handle


# get all images
print "Getting all images"
all_images = list( fedoraHandles.fedora_handle.risearch.get_subjects('info:fedora/fedora-system:def/relations-external#hasContentModel','info:fedora/CM:Image') )

# iterate through
for index, PID in enumerate(all_images):

	try:
		print "Working on",PID,"/",index,len(all_images)

		obj_handle = WSUDOR_ContentTypes.WSUDOR_Object(object_type="WSUDOR",payload=PID)

		# iterate through
		for DS in obj_handle.objMeta['datastreams']:
			print "\tWorking on",DS['ds_id']

			# write RELS-INT relationship
			print "WRITING RELS-INT"
			result = fedora_handle.api.addRelationship(obj_handle.ohandle,'info:fedora/{PID}/{ds_id}_ACCESS'.format(PID=obj_handle.ohandle.pid,ds_id=DS['ds_id']),'info:fedora/fedora-system:def/relations-internal#isAccessOf','info:fedora/{PID}'.format(PID=obj_handle.ohandle.pid))
			print result

	except Exception,e:
		print "Had a problem with",PID
		print str(e)
		fhand = open('accessErrors.txt','a')
		msg_string = PID+"\n"
		fhand.write(msg_string)
		fhand.close()




	# # DEBUG
	# if index == 0:
	# 	break





