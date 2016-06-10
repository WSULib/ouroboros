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



# Loris Info
@WSUDOR_API_app.route("/%s/bitStream/loris/<id>/info.json" % (localConfig.WSUDOR_API_PREFIX), methods=['POST', 'GET'])
def loris_info(id):

	print dir(request)

	loris_url = "http://localhost/loris_local/%s/info.json" % (id)
	print loris_url
	r = requests.get(loris_url).json()
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



def stream_loris(r,length):
	step = 1024
	for chunk in range(0, length, step):
		yield r.iter_content(step).next()