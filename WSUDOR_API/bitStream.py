# Ouroboros config
import localConfig

# flask proper
from flask import request, redirect, Response, jsonify, stream_with_context

# WSUDOR_API_app
from WSUDOR_API import WSUDOR_API_app
from WSUDOR_Manager import fedora_handle, redisHandles

from eulfedora.models import DatastreamObject, XmlDatastreamObject

import requests
import json
import uuid
import hashlib
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

	# stored in redis
	unique_id = hashlib.md5(PID+DS).hexdigest()

	try:
		
		# get object
		obj_handle = fedora_handle.get_object(PID)
		# object does not exist
		if not obj_handle.exists:
			return msg_and_code("object does not exist", 404)

		# get datastream
		obj_ds_handle = obj_handle.getDatastreamObject(DS)
		# datastream does not exist
		if not obj_ds_handle.exists:
			return msg_and_code("datastream does not exist", 404)

			
		# blocked datastream
		if DS not in localConfig.UNBLOCKED_DATASTREAMS:

			key = request.args.get('key', '')
			token = request.args.get('token', False)
			print {"key":key,"token":token}


			# if key match, and token request, return token
			if key == localConfig.BITSTREAM_KEY and token == 'request':
				
				# create unique token with hash, PID, and datastream
				# token = hashlib.md5(localConfig.BITSTREAM_SALT + PID + DS).hexdigest()
				token = str(uuid.uuid4()) # random token
				print "setting token: %s" % token
				redisHandles.r_catchall.set(token, unique_id)
				return msg_and_code({"token":token},200)


			# if key match, no token, return ds
			if key == localConfig.BITSTREAM_KEY and not token:
				return return_ds(obj_ds_handle)


			# if key match, but no token stored, return error
			if key == localConfig.BITSTREAM_KEY and not redisHandles.r_catchall.get(token):
				return msg_and_code('invalid token provided, remove if providing key as well',401)


			# if key, and stored token, and PID/DS associated with token
			if key == localConfig.BITSTREAM_KEY and redisHandles.r_catchall.get(token) == unique_id:
				return return_ds(obj_ds_handle)


			if key and key != localConfig.BITSTREAM_KEY:
				return msg_and_code('incorrect key',401)

			
			if not key and token:
				'''
				check if token is key in redis 
					if so, delete key and return ds
						OR, keep and remove after certain time?
					if not, return error
				'''
				if redisHandles.r_catchall.get(token) == unique_id:
					print 'token verified for obj/ds, removing token: %s' % token
					redisHandles.r_catchall.delete(token)
					return return_ds(obj_ds_handle)				 
				else:
					return msg_and_code("token not found or does not match object and datastream",401)

			# all else, no keys or tokens, indicated datastream is blocked
			return msg_and_code("datastream is blocked", 403)

		# if made this far, stream response
		return return_ds(obj_ds_handle)
		
	except Exception, e:
		print e
		return msg_and_code('bitStream failed',500)


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
def msg_and_code(msg,status_code):
	response = jsonify({"response":msg})
	response.status_code = status_code
	return response


def return_ds(obj_ds_handle):
	return Response(stream_ds(obj_ds_handle), mimetype=obj_ds_handle.mimetype)


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





