# Ouroboros config
import localConfig

# flask proper
from flask import request, redirect, Response, jsonify

# WSUDOR_API_app
from WSUDOR_API import WSUDOR_API_app
from WSUDOR_Manager import fedora_handle

from eulfedora.models import DatastreamObject, XmlDatastreamObject


'''
Small utility to serve unblocked datastreams from Fedora, including:
	- DC, MODS, RELS-EXT, COLLECTIONPDF, etc.

Requires a 'UNBLOCKED_DATASTREAMS' setting in localConfig
'''

def return_error(msg,status_code):
		response = jsonify({"msg":msg})
		response.status_code = status_code
		return response

# bitStream
#########################################################################################################
@WSUDOR_API_app.route("/%s/bitStream/<PID>/<DS>" % (localConfig.WSUDOR_API_PREFIX), methods=['POST', 'GET'])
def bitStream(PID,DS):

	try:
		
		# get object
		obj_handle = fedora_handle.get_object(PID)
		# object does not exist
		if not obj_handle.exists:
			return return_error("object does not exist", 404)

		# get datastream
		obj_ds_handle = obj_handle.getDatastreamObject(DS)
		# datastream does not exist
		if not obj_ds_handle.exists:
			return return_error("datastream does not exist", 404)
			
		# both exist, and unblocked
		if DS not in localConfig.UNBLOCKED_DATASTREAMS:
			return return_error("datastream is blocked", 403)

		# return datastream
		# chunked, generator
		def stream():
			step = 1024
			pointer = 0

			# File Type
			if type(obj_ds_handle) == DatastreamObject:
				for chunk in range(0, len(obj_ds_handle.content), step):
					yield obj_ds_handle.content[chunk:chunk+step]

			# XML Type
			if type(obj_ds_handle) == XmlDatastreamObject:
				for chunk in range(0, len(obj_ds_handle.content.serialize()), step):
					yield obj_ds_handle.content.serialize()[chunk:chunk+step]

		return Response(stream(), mimetype=obj_ds_handle.mimetype)

	except:
		return return_error('bitStream failed',500)










