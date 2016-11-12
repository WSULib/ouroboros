# -*- coding: utf-8 -*-
# WSUDOR_API : models.py


# python modules
import time

# Ouroboros config
import localConfig

# modules
from flask_restful import abort, fields, reqparse, Resource

# WSUDOR_API_app
from WSUDOR_API import api

# WSUDOR_Manager
from WSUDOR_ContentTypes import WSUDOR_Object
from WSUDOR_Manager.solrHandles import solr_handle


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
			response = ResponseObject(200, body, headers)

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
				'response_time': time.time() - self.stime,
			},
			'response': self.body,
		}, self.status_code, self.headers



# ITEMS
#################################################################################
class Item(Resource):

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



# COLLECTIONS
#################################################################################




# SEARCH
#################################################################################
class SolrSearch(object):

	'''
	desc: container for solr search params, hasmethod for returning dictionary
	that is sent to solr_handle
	'''

	# default ordered facets, can be overridden
	ordered_facets = [
	  	"rels_hasContentModel",
	  	"rels_isMemberOfCollection",  	
	  	"facet_mods_year",
	  	"dc_subject",
	  	"dc_creator",
	  	"dc_coverage",
	  	"dc_language",
	  	"dc_publisher" 	  	
	  ]


	def __init__(self, q='*:*', facet_list=ordered_facets, sort='id', rows=10, start=0):
		self.q = q
		self.facet_list = facet_list
		self.sort = sort
		self.rows = rows
		self.start = start


	def as_dictionary(self):
		return self.__dict__



class Search(Resource):

	'''
	desc: primary search class, prepared to handle general search, collection search,
	and searching within items
	'''


	def get(self):

		# init parser
		parser = reqparse.RequestParser(bundle_errors=True)

		# parse args
		parser.add_argument('q', type=str, help='provide a solr search string')
		parser.add_argument('facet_list', type=str, action='append', help='list of facets to return with response')
		parser.add_argument('sort', type=str, help='field to sort by') # add multiple for tiered sorting?
		parser.add_argument('rows', type=int, help='integer of number of rows to return')
		parser.add_argument('start', type=int, help='integer for start of rows in response')
		args = parser.parse_args()
		print args

		# build SolrSearch object
		# solr_search = SolrSearch(
		# 	q = args['q']
		# )

		# init ResponseObject
		response = ResponseObject()

		# query Solr
		# query dictionary (qd)
		qd = {}

		# query string
		qd['q'] = ["*:*"]

		# Send and return query
		sr = solr_handle.search(**qd)

		# build response
		response.status_code =200
		response.body = {
			'solr_results': sr.raw_content
		}
		return response.generate_response()



# TESTING
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