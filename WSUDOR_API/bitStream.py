# Ouroboros config
import localConfig

# flask proper
from flask import request, redirect, Response, jsonify, stream_with_context

# WSUDOR_API_app
from WSUDOR_API import WSUDOR_API_app
from WSUDOR_Manager import fedora_handle

from eulfedora.models import DatastreamObject, XmlDatastreamObject

import requests
import json
from contextlib import closing


'''
Small utility to serve unblocked datastreams from Fedora, including:
	- DC, MODS, RELS-EXT, COLLECTIONPDF, etc.

Requires a 'UNBLOCKED_DATASTREAMS' setting in localConfig
'''

'''
Update: with this loris proxy, requires some changes in apache (see 000-default.conf)
Gist is that loris is now at /loris_local, and /loris reroutes to /WSUAPI/bitStream/loris
'''

# bitStream
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

		# if made this far, stream response
		return Response(stream_ds(obj_ds_handle), mimetype=obj_ds_handle.mimetype)

	except:
		return return_error('bitStream failed',500)


# Loris Info
@WSUDOR_API_app.route("/%s/bitStream/loris/<id>/info.json" % (localConfig.WSUDOR_API_PREFIX), methods=['POST', 'GET'])
def loris_info(id):

	r = requests.get("http://localhost/loris_local/%s/info.json" % (id)).json()
	return jsonify(r)



# Loris Image API
'''
{scheme}://{server}{/prefix}/{identifier}/{region}/{size}/{rotation}/{quality}.{format}
'''
@WSUDOR_API_app.route("/%s/bitStream/loris/<id>/<region>/<size>/<rotation>/<quality>.<format>" % (localConfig.WSUDOR_API_PREFIX), methods=['POST', 'GET'])
def loris_image(id,region,size,rotation,quality,format):

	# build url (move this to IIIF class)
	loris_url = "http://localhost/loris_local/%s/%s/%s/%s/%s.%s" % (id, region, size, rotation, quality, format)
	print loris_url
	r = requests.get(loris_url, stream=True)
	# print r.headers

	# stream_with_context
	# http://flask.pocoo.org/snippets/118/
	# return Response(stream_with_context(r.iter_content(chunk_size=1024)), content_type=r.headers['Content-Type'], mimetype=r.headers['Content-Type'])

	# stream with iterator function
	length = int(r.headers['Content-Length'])
	return Response(stream_loris(r,length), mimetype=r.headers['Content-Type'])


# helpers
def return_error(msg,status_code):
		response = jsonify({"msg":msg})
		response.status_code = status_code
		return response


# chunked, generator
def stream_ds(obj_ds_handle):
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


def stream_loris(r,length):
	step = 1024
	for chunk in range(0, length, step):
		yield r.iter_content(step).next()





