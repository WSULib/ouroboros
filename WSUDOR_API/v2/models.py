# -*- coding: utf-8 -*-
# WSUDOR_API : models.py

# python modules
import time

# Ouroboros config
import localConfig

# modules
from flask import redirect
import flask_restful
from flask_restful import abort, fields, reqparse, Resource

# WSUDOR_Manager
from WSUDOR_ContentTypes import WSUDOR_Object
from WSUDOR_Manager.solrHandles import solr_handle
from WSUDOR_Manager import db
from WSUDOR_Manager.models import User

# API
from inc.bitStream import BitStream
from inc.lorisProxy import loris_image, loris_info
from inc.iiif_manifest import iiif_manifest, iiif_annotation_list


# ResponseObject
#################################################################################

class ResponseObject(object):

	'''
	This can be built in one of two ways:
		1) init empty, and build up
			response = ResponseObject()
			response.status_code = 200
			response.body = { 'goober':'tronic' }
			response.headers = { 'X-Powered-By':'custom headers' }

		2) init with code, body, and headers already compiled:
			response = ResponseObject(status_code=200, body={}, headers={})

	Then use generate_response() method to return:
		return response.generate_response()
	'''

	def __init__(self, status_code=None, headers={}, body={} ):
		self.status_code = status_code
		self.headers = headers
		self.stime = time.time()
		self.body = body

		# add custom X-Powered-By headers
		self.headers['X-Powered-By'] = ['ShoppingHorse','DumpsterTurkey']


	def generate_response(self):

		return {
			'header':{
				'api_response_time': time.time() - self.stime,
			},
			'response': self.body,
		}, self.status_code, self.headers


# Identify
#################################################################################
class Identify(Resource):

	'''
	desc: returns generic API information	
	'''

	def get(self):

		# init ResponseObject
		response = ResponseObject(status_code=200, body={
			'identify':'WSUDOR API',
			'documentation':'https://github.com/WSULib/ouroboros/blob/v2/WSUDOR_API/v2/README.md'
		})
		return response.generate_response()



# Items
#################################################################################
class ItemMetadata(Resource):

	'''
	desc: returns full metadata information for a single item
	expects: PID of item to retrieve
	'''

	def __init__(self, *args, **kwargs):
		self.content_type_specific = []


	def get(self, pid):

		# init ResponseObject
		response = ResponseObject()

		# abort if no pid
		if not pid:
			abort(400, message='please provide a pid')

		# get object
		obj = WSUDOR_Object(pid)
		if not obj:
			abort(404, message='%s not found' % pid)	

		# determine content-type
		try:
			ct = obj.SolrDoc.asDictionary()['rels_preferredContentModel'][0].split('/')[-1].split(':')[-1]
		except:
			print "could not determine content type, setting None"
			ct = None

		# run content-type api additions
		for f in obj.public_api_additions:
			self.content_type_specific.append({
				f.__name__:f() # name of content_type function: function output
			})

		# build response
		response.status_code =200
		response.body = {
			'pid': pid,
			'content_type': ct,
			'solr_doc': obj.SolrDoc.asDictionary(),
			'collections': obj.isMemberOfCollections,
			'learning_objects': obj.hasLearningObjects,
			'hierarchical_tree': obj.hierarchicalTree,
			'content_type_specific': self.content_type_specific
		}
		return response.generate_response()


class ItemFile(Resource):

	'''
	desc: returns full metadata information for a single item
	expects: PID of item to retrieve
	'''

	def get(self, pid, datastream):

		# init ResponseObject
		response = ResponseObject()

		# abort if no pid
		if not pid:
			abort(400, message='please provide a pid')

		# get object
		obj = WSUDOR_Object(pid)
		if not obj:
			abort(404, message='%s not found' % pid)

		# init parser
		parser = reqparse.RequestParser(bundle_errors=True)

		# parse args
		parser.add_argument('key', type=str, help='expecting secret download key', default=False)
		parser.add_argument('token', type=str, help='expecting download one-use token ', default=False)
		parser.add_argument('download', type=flask_restful.inputs.boolean, help='if set, download headers are sent', default=False)
		args = parser.parse_args()

		# init BitStream
		bs = BitStream(pid, datastream, key=args['key'], token=args['token'], download=args['download'])
		return bs.stream()


class ItemThumbnail(Resource):

	'''
	desc: Return thumbnail for item
	expecting: pid, delivery_mechanism
	'''

	def __init__(self,**kwargs):
		self.delivery_mechanism = kwargs['delivery_mechanism']

	def get(self, pid):

		# init ResponseObject
		response = ResponseObject()

		# abort if no pid
		if not pid:
			abort(400, message='please provide a pid')

		# get object
		obj = WSUDOR_Object(pid)
		if not obj:
			abort(404, message='%s not found' % pid)

		# init parser
		parser = reqparse.RequestParser(bundle_errors=True)

		# BitStream
		if self.delivery_mechanism.lower() == 'bitstream':
			bs = BitStream(pid, 'THUMBNAIL')
			return bs.stream()

		# Loris
		if self.delivery_mechanism.lower() == 'loris':
			return loris_image(
				image_id = 'fedora:%s|THUMBNAIL' % pid,
				region = 'full',
				size = 'full',
				rotation = '0',
				quality = 'default',
				format = 'png'
			)


class ItemLoris(Resource):

	'''
	desc: Returns datastream via loris	
	'''

	def get(self, pid, datastream, region, size, rotation, quality, format):

		# init ResponseObject
		response = ResponseObject()

		# abort if no pid
		if not pid:
			abort(400, message='please provide a pid')

		# get object
		obj = WSUDOR_Object(pid)
		if not obj:
			abort(404, message='%s not found' % pid)

		# init parser
		parser = reqparse.RequestParser(bundle_errors=True)

		# Loris
		return loris_image(
			image_id = 'fedora:%s|%s' % (pid,datastream),
			region = region,
			size = size,
			rotation = rotation,
			quality = quality,
			format = format
		)


class ItemLoris(Resource):

	'''
	desc: Returns datastream via loris	
	'''

	def get(self, pid, datastream, region=None, size=None, rotation=None, quality=None, format=None):

		# init ResponseObject
		response = ResponseObject()

		# abort if no pid
		if not pid:
			abort(400, message='please provide a pid')

		# get object
		obj = WSUDOR_Object(pid)
		if not obj:
			abort(404, message='%s not found' % pid)

		# set image id
		image_id = 'fedora:%s|%s' % (pid,datastream)

		# if loris params are None, assume info.json requested
		# if region == size == rotation == quality == format == None:
		if all(e==None for e in [region,size,rotation,quality,format]):
			return loris_info(image_id)

		# Loris
		else:
			return loris_image(
				image_id = image_id,
				region = region,
				size = size,
				rotation = rotation,
				quality = quality,
				format = format
			)


class ItemIIIF(Resource):

	'''
	desc: Returns datastream via loris	
	'''

	def get(self, pid, annotation_list=False):

		# init ResponseObject
		response = ResponseObject()

		# abort if no pid
		if not pid:
			abort(400, message='please provide a pid')

		# get object
		obj = WSUDOR_Object(pid)
		if not obj:
			abort(404, message='%s not found' % pid)

		if annotation_list:
			return iiif_annotation_list(pid)

		else:
			return iiif_manifest(pid)



# Search
#################################################################################
class SolrSearch(object):

	'''
	Class for capturing request args and setting container for search params
	'''

	# order from https://wiki.apache.org/solr/CommonQueryParameters
	# expose this configuration to localConfig.py?
	default_params = { 
		'q': '*:*',
		'sort': None,
		'start': 0,
		'rows': 10,
		'fq': [],
		'fl': [ "id", "mods*", "dc*", "rels*", "obj*", "last_modified"],
		'facet': False,
		'facet.mincount': 1,
		'facet.limit': -1,
		'facet.field': [],
		'wt': 'json',
	}


	def __init__(self):

		self.params = {}

		# capture request args
		self.capture_request_args()

		# include defaults if skip_defaults is not present, or False
		if not self.skip_defaults:
			self.params.update(self.default_params)

		# merge defaults with overrides from client
		self.params.update(self.args)

		# confirm that id is always in fl
		if 'id' not in self.params['fl']:
			self.params['fl'].append('id')

		# DEBUG
		print self.params

		# flip on facets of fields requested
		if 'facet.field' in self.params and len(self.params['facet.field']) > 0:
			self.params['facet'] = True


	def capture_request_args(self):

		# using request arg parsing from flask-restful
		# http://flask-restful-cn.readthedocs.io/en/0.3.5/reqparse.html

		# init parser
		parser = reqparse.RequestParser(bundle_errors=True)

		# parse args
		parser.add_argument('q', type=str, help='expecting solr search string')
		parser.add_argument('fq', type=str, action='append', help='expecting filter query (fq) (multiple)')
		parser.add_argument('fl', type=str, action='append', help='expecting field limiter (fl) (multiple)')
		parser.add_argument('facet.field', type=str, action='append', help='expecting field to return as facet (multiple)')
		parser.add_argument('sort', type=str, help='expecting field to sort by') # add multiple for tiered sorting?
		parser.add_argument('rows', type=int, help='expecting integer for number of rows to return')
		parser.add_argument('start', type=int, help='expecting integer for where to start in results')
		parser.add_argument('wt', type=str, help='expecting string for return format (e.g. json, xml, csv)')
		parser.add_argument('skip_defaults', type=flask_restful.inputs.boolean, help='true / false: if set false, will not load default solr params', default=False)
		args = parser.parse_args()

		# pop select fields from args
		self.skip_defaults = args['skip_defaults']
		del args['skip_defaults']

		# remove None values from args
		self.args = dict((k, v) for k, v in args.iteritems() if v != None)


	def execute_search(self, include_item_metadata=True):
		self.search_results = solr_handle.search(**self.params)
		if include_item_metadata:
			self.interleave_item_metadata()


	def interleave_item_metadata(self):
		# inteleave single item metadata URLs
		for doc in self.search_results.raw_content['response']['docs']:
			doc['item_metadata'] = 'http://%s/WSUAPI/item/%s' % (localConfig.APP_HOST,doc['id'])



class Search(Resource):

	'''
	desc: primary search class, prepared to handle general search
	'''

	def get(self):

		# init ResponseObject
		response = ResponseObject()

		# build SolrSearch object
		solr_search = SolrSearch()

		# execute query
		solr_search.execute_search()

		# build response
		response.status_code =200
		response.body = {
			'solr_results': solr_search.search_results.raw_content
		}
		return response.generate_response()



class CollectionSearch(Resource):

	'''
	desc: collection search class, prepared to search within a single collection
	expects: collection pid
	'''

	def get(self, pid):

		# init ResponseObject
		response = ResponseObject()

		# build SolrSearch object
		solr_search = SolrSearch()

		# add collection pid to fq
		if 'fq' not in solr_search.params:
			solr_search.params['fq'] = []
		solr_search.params['fq'].append('rels_isMemberOfCollection:info\:fedora/%s' % pid.replace(":","\:"))

		# execute query
		solr_search.execute_search()

		# build response
		response.status_code =200
		response.body = {
			'solr_results': solr_search.search_results.raw_content
		}
		return response.generate_response()


# Users
#################################################################################
class UserWhoami(Resource):

	def get(self, username):

		'''
		expecting username, returns Ouroboros account info
		'''

		# init ResponseObject
		response = ResponseObject()

		exists = db.session.query(db.exists().where(User.username == username)).scalar()

		if exists:

			user = User.get(username)

			# build response
			response.status_code =200
			response.body = {
					'username':username,
					'exists':True,
					'roles':user.role
				}

		else:

			# build response
			response.status_code =404
			response.body = {
					'username':username,
					'exists':False,
				}

		# return response		
		return response.generate_response()

		
# Testing
#################################################################################
class HelloWorld(Resource):

	def get(self, name):

		'''
		expecting variable based on route from views.py
		also, triggers abort() if match
		'''

		if name.lower() == 'shoppinghorse':
			abort(400, message='ANYONE but ShoppingHorse...')
		return {'hello': name}


class ArgParsing(Resource):

	def get(self):
		parser = reqparse.RequestParser(bundle_errors=True)
		parser.add_argument('goober', type=int, help='the particular integrity of goober')
		parser.add_argument('tronic', type=int, help='pecularities of tronic')
		parser.add_argument('color', type=str, help='the colors, the COLORS.', action='append', dest='colors')
		args = parser.parse_args(strict=True)

		'''
		- If it 'goober' fails the type=int restriction above, it aborts here and returns a 400 with message = help from above
		- if include strict=True in parser.parse_args, squawks if anything but 'goober' or 'tronic' in GET/POST params
		- multiple values: action='append' above allows for natural list creation, AND kicks it to new variable name (makes sense for pluralizing)
		- bundle_errors=True groups errors in response
		- and for good measure, let's include the endpoint!
		'''

		return {
			'goober_integrity': args['goober'],
			'pecularities_of_tronic': args['tronic'],
			'bevy_of_colors': args['colors']
		}