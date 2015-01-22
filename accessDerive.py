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

		for DS in obj_handle.objMeta['datastreams']:
			print "\tWorking on",DS['ds_id']

			if obj_handle.ohandle.getDatastreamObject( DS['ds_id']).exists == False:
				continue

			file = cStringIO.StringIO(obj_handle.ohandle.getDatastreamObject( DS['ds_id']).content )

			# make ACCESS ds
			temp_filename = "/tmp/Ouroboros/"+str(uuid.uuid4())+".jpg"
			im = Image.open(file)
			if im.mode != "RGB":
				im = im.convert("RGB")
			im.save(temp_filename,'JPEG')
			access_handle = eulfedora.models.FileDatastreamObject(obj_handle.ohandle, "{ds_id}_ACCESS".format(ds_id=DS['ds_id']), "{label}_ACCESS".format(label=DS['label']), mimetype="image/jpeg", control_group='M')
			access_handle.label = "{label}_ACCESS".format(label=DS['label'])
			access_handle.content = open(temp_filename)
			access_handle.save()
			os.system('rm {temp_filename}'.format(temp_filename=temp_filename))


	except:
		print "Had a problem with",PID
		fhand = open('accessErrors.txt','a')
		msg_string = PID+"\n"
		fhand.write(msg_string)




	# # DEBUG
	# if index == 0:
	# 	break





