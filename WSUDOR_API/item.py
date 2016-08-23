# -*- coding: utf-8 -*-
# WSUDOR Object-Centric API

'''
All routes extend host/item
'''

# Ouroboros config
import localConfig

# WSUDOR_API_app
from WSUDOR_API import WSUDOR_API_app
from bitStream import BitStream
from lorisProxy import loris_image

# general
from flask import request, redirect, Response, jsonify, stream_with_context
import requests


# Item root, redirect
@WSUDOR_API_app.route("/item/<pid>", methods=['POST', 'GET'])
@WSUDOR_API_app.route("/item/<pid>/", methods=['POST', 'GET'])
def item(pid):	

	# redirect to digital collections page
	return redirect("https://%s/digitalcollections/item?id=%s" % (localConfig.APP_HOST, pid), code=302)


# Item Thumbnail
# e.g. https://digital.library.wayne.edu/loris/fedora:wayne:CFAIEB01c010%7CTHUMBNAIL/full/full/0/default.png
@WSUDOR_API_app.route("/item/<pid>/thumbnail", methods=['POST', 'GET'])
@WSUDOR_API_app.route("/item/<pid>/thumbnail/", methods=['POST', 'GET'])
def item_thumbnail(pid):

	return loris_image(
		image_id = 'fedora:%s|THUMBNAIL' % pid,
		region = 'full',
		size = 'full',
		rotation = 0,
		quality = 'default',
		format = 'png'
		)

	# # generate URL
	# url = "http://localhost/loris/fedora:%s|THUMBNAIL/full/full/0/default.png" % (pid)	
	# r = requests.get(url, stream=True)

	# # stream_with_context
	# # http://flask.pocoo.org/snippets/118/
	# return Response(r.iter_content(chunk_size=localConfig.LORIS_STREAM_CHUNK_SIZE), content_type=r.headers['Content-Type'])


# Datastream Wrapper for bitStream
@WSUDOR_API_app.route("/item/<pid>/bitStream/<datastream>", methods=['POST', 'GET'])
@WSUDOR_API_app.route("/item/<pid>/bitStream/<datastream>/", methods=['POST', 'GET'])
def item_datastream(pid,datastream):

	'''
	Wrapper for bitStream via BitStream class
	Passes along potential 'key' and 'token' GET parameters for bitStream
	'''

	bs = BitStream(request, pid , datastream)
	return bs.stream()


