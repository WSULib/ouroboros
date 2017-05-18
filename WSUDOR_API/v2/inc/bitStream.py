# Ouroboros config
import localConfig

# flask proper
from flask import request, redirect, Response, jsonify, stream_with_context, Blueprint

# WSUDOR_API_app
from WSUDOR_Manager import fedora_handle, redisHandles
from WSUDOR_Manager.utilities import mimetypes
from WSUDOR_API import logging
logging = logging.getChild('bitStream')

from eulfedora.models import DatastreamObject, XmlDatastreamObject

import requests
import json
import uuid
import hashlib
from contextlib import closing

bitStream_blueprint = Blueprint('bitStream_v2', __name__)

'''
Small utility to serve unblocked datastreams from Fedora, including:
	- DC, MODS, RELS-EXT, COLLECTIONPDF, etc.

Requires a 'UNBLOCKED_DATASTREAMS' setting in localConfig
Accepts keys and tokens for access (see doc/bitStream.md)
'''

# BitStream model to handle bitStream requests
class BitStream(object):

	def __init__(self, PID, DS, key=None, token=None, download=False):

		# object and datastream
		self.PID = PID
		self.DS = DS
		self.unique_id = hashlib.md5(PID+DS).hexdigest()		
		
		# auth, key, token access
		self.key = key
		self.token = token
		self.return_token = None

		# response params
		self.msg = None
		self.status_code = None
		self.download = download

		# stream params
		self.chunk_step = 1024

		# instantiate object
		self.obj_handle = fedora_handle.get_object(self.PID)
		self.obj_ds_handle = self.obj_handle.getDatastreamObject(self.DS)

		# determine auth
		try:
			self.auth = self._determine_auth()
		except Exception, e:
			logging.debug(e)
			self.msg = "authorization failed"
			self.status_code = 500
			self.auth = False

	
	# return custom message and HTTP status code
	def return_message(self):
		response = jsonify({"response":self.msg})
		response.status_code = self.status_code
		return response


	# on auth, stream datastream
	def return_datastream(self):
		'''
		Can we set headers here?
		Content-Disposition: attachment; filename=FILENAME
		'''
		response = Response(self.streamGen(), mimetype=self.obj_ds_handle.mimetype)

		# if download flag present, add headers that force download and filename
		if self.download:
			file_ext = mimetypes.guess_extension(self.obj_ds_handle.mimetype)
			if file_ext == '.jpe':
				file_ext = '.jpg'
			response.headers['Content-Disposition'] = 'attachment; filename=%s%s' % (self.DS, file_ext)

		# return response
		return response


	# chunked, stream generator
	def streamGen(self):

		# File Type
		if type(self.obj_ds_handle) == DatastreamObject:
			for chunk in range(0, len(self.obj_ds_handle.content), self.chunk_step):
				yield self.obj_ds_handle.content[chunk:chunk+self.chunk_step]

		# XML Type
		if type(self.obj_ds_handle) == XmlDatastreamObject:
			for chunk in range(0, len(self.obj_ds_handle.content.serialize()), self.chunk_step):
				yield self.obj_ds_handle.content.serialize()[chunk:chunk+self.chunk_step]


	# primary method for streaming
	def stream(self):
		
		if self.auth:
			return self.return_datastream()
		else:
			return self.return_message()


	# method for checking auth, setting msgs and HTTP code if not
	def _determine_auth(self):
					
		# if no object, fail auth
		if not self.obj_handle.exists:
			self.msg = "object does not exist"
			self.status_code = 404
			return False

		# datastream does not exist
		if not self.obj_ds_handle.exists:
			self.msg = "datastream does not exist"
			self.status_code = 404
			return False
			
		# decision tree for blocked datastream
		if self.DS not in localConfig.UNBLOCKED_DATASTREAMS:

			# if key present, overrides most token considerations
			if self.key:

				# if key and key match
				if self.key == localConfig.BITSTREAM_KEY:

					# if key match, and token request, return token
					if self.token == 'request':
						
						return_token = str(uuid.uuid4()) # random token
						logging.debug("setting token: %s" % return_token)
						redisHandles.r_catchall.set(return_token, self.unique_id)
						self.msg = {
							"token":return_token,
							"url":"https://%s/item/%s/file/%s/?token=%s" % (localConfig.APP_HOST, self.PID, self.DS, return_token),
							"object":self.PID,
							"datastream":self.DS
						}
						self.status_code = 200
						return False

					# if key match, regardless of token, return ds
					else:
						return True

				# if key but no match
				if self.key != localConfig.BITSTREAM_KEY:
					self.msg = "incorrect key"
					self.status_code = 401
					return False
		
			# if token present
			elif self.token:

				if not redisHandles.r_catchall.get(self.token):
					self.msg = "token not found"
					self.status_code = 401
					return False

				elif redisHandles.r_catchall.get(self.token) == self.unique_id:
					'''
					check if token is key in redis 
						if so, delete key and return ds
							OR, keep and remove after certain time?
						if not, return error
					'''
					logging.debug('token verified for obj/ds, removing token: %s' % self.token)
					redisHandles.r_catchall.delete(self.token)
					return True

				elif redisHandles.r_catchall.get(self.token) != self.unique_id:
					self.msg = "token found, but does not match object and datastream"
					self.status_code = 401
					return False

				else:
					self.msg = "problem with token"
					self.status_code = 500
					return False
			
			# if it's an MP3
			elif "_MP3" in self.DS:
				return True
			
			# all else, no keys or tokens, indicated datastream is blocked
			else:
				self.msg = "datastream is blocked"
				self.status_code = 403
				return False

		# if made this far, stream response
		else:
			self.msg = {
				"token":None,
				"url":"https://%s/item/%s/file/%s/?" % (localConfig.APP_HOST, self.PID, self.DS),
				"object":self.PID,
				"datastream":self.DS			
			}
			self.status_code = 200
			return True


	@classmethod
	def genAllTokens(cls, PID, key):
		
		'''
		This function generates bitStream tokens for ALL datastreams for an object
		'''

		# if key and key match
		if key == localConfig.BITSTREAM_KEY:

			logging.debug("generating all bitStream tokens...")

			# return dict
			response_dict = {}

			# init object handle
			obj_handle = fedora_handle.get_object(PID)

			# generate tokens for each datastream using BitStream instance
			for DS in obj_handle.ds_list:

				try:

					bs = cls(PID, DS, key=key, token='request')
					response_dict[DS] = {
						"token":bs.msg['token'],
						"url":bs.msg['url']
					}

				except:
					
					logging.debug("could not generate bitstream for %s" % DS)
					response_dict[DS] = {
						'msg': "could not generate bitstream for %s" % DS
					}

			return response_dict

		else:
			logging.debug("bitstream key not recognized")
			return False


# bitStream
@bitStream_blueprint.route("/bitStream/<PID>/<DS>", methods=['POST', 'GET'])
def bitStream(PID,DS):

	# extract key and token if present
	key = request.args.get('key', False)
	token = request.args.get('token', False)
	download = request.args.get('download', False)

	# init BitStream
	bs = BitStream(PID,DS,key=key, token=token, download=download)
	return bs.stream()







