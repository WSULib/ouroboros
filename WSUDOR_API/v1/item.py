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
from flask import request, redirect, Response, jsonify, stream_with_context, Blueprint
import requests

item_blueprint = Blueprint('item_v1', __name__)

# Item root, redirect
@item_blueprint.route("/item/<pid>", methods=['POST', 'GET'])
@item_blueprint.route("/item/<pid>/", methods=['POST', 'GET'])
def item(pid):	

	# redirect to digital collections page
	return redirect("https://%s/digitalcollections/item?id=%s" % (localConfig.APP_HOST, pid), code=302)


# Item Thumbnail
# e.g. https://digital.library.wayne.edu/loris/fedora:wayne:CFAIEB01c010%7CTHUMBNAIL/full/full/0/default.png
@item_blueprint.route("/item/<pid>/thumbnail", methods=['POST', 'GET'])
@item_blueprint.route("/item/<pid>/thumbnail/", methods=['POST', 'GET'])
def item_thumbnail(pid):

	return loris_image(
		image_id = 'fedora:%s|THUMBNAIL' % pid,
		region = 'full',
		size = 'full',
		rotation = '0',
		quality = 'default',
		format = 'png'
		)


# Datastream Wrapper for bitStream
@item_blueprint.route("/item/<pid>/bitStream/<datastream>", methods=['POST', 'GET'])
@item_blueprint.route("/item/<pid>/bitStream/<datastream>/", methods=['POST', 'GET'])
def item_datastream(pid,datastream):

	'''
	Wrapper for bitStream via BitStream class
	Passes along potential 'key' and 'token' GET parameters for bitStream
	'''

	# extract key and token if present
	key = request.args.get('key', False)
	token = request.args.get('token', False)
	download = request.args.get('download', False)

	bs = BitStream(pid, datastream, key=key, token=token, download=download)
	return bs.stream()



