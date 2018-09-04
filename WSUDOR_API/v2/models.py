# -*- coding: utf-8 -*-
# WSUDOR_API : models.py

# python modules
from lxml import etree
import pdb
import re
import time

# Ouroboros config
import localConfig

# Logging
from WSUDOR_API import logging

# modules
from flask import request, redirect, Response
import flask_restful
from flask_restful import abort, fields, reqparse, Resource

# WSUDOR_Manager
from WSUDOR_ContentTypes import WSUDOR_Object
from WSUDOR_Manager import fedora_handle
from WSUDOR_Manager.solrHandles import solr_handle
from WSUDOR_Manager import db
from WSUDOR_Manager.models import User

# API
import utilities
from inc.bitStream import BitStream
from inc.lorisProxy import loris_image, loris_info
from inc.iiif_manifest import iiif_manifest, iiif_annotation_list
from inc.oai import OAIProvider


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

		# check for precision return
		parser = reqparse.RequestParser(bundle_errors=True)
		parser.add_argument('cherrypick', type=str, default=False)
		args = parser.parse_args()		

		# if cherrypick present, return cherrypick of full API response
		if args['cherrypick']:

			# get hops			
			hops = args['cherrypick'].split(".")

			# compile regex
			ai_regex = re.compile(r'(.+?)\[([0-9]+)\]')

			# loop through hops
			for hop in hops:

				# check to see if ends with array index
				ai_check = re.match(ai_regex, hop)
				if ai_check:
					self.body = self.body.get(ai_check.group(1), False)
					if self.body == False:
						break
					try:
						self.body = self.body[int(ai_check.group(2))]
					except IndexError:
						self.body = False

				else:
					self.body = self.body.get(hop, False)
					if self.body == False:
						break

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
class Item(Resource):

	'''
	desc: generic item class extended by others
	expects: 
		PID of item to retrieve
		skip_check = if True, will skip checking or loading object entirely
		skip_load = if True, will only check for existence in Fedora, not load WSUDOR Object (slower)
	'''

	def __init__(self, pid, skip_check=False, skip_load=False):

		# abort if no pid
		if not pid:
			abort(400, message='please provide a pid')

		# get object if not yet set
		if not skip_check:
			if skip_load:
				logging.debug("skipping WSUDOR object load, checking instance in Fedora")
				self.obj = fedora_handle.get_object(pid).exists
				if not self.obj:
					abort(404, message='%s not found in Fedora' % pid)
			else:
				logging.debug("loading as WSUDOR object")
				self.obj = WSUDOR_Object(pid)
				if not self.obj:
					abort(404, message='%s not found' % pid)
		else:
			logging.debug('skipping item check and load')


	def get_item_metadata(self):

		# determine content-type
		try:
			ct = self.obj.SolrDoc.asDictionary()['rels_preferredContentModel'][0].split('/')[-1].split(':')[-1]
		except:
			logging.debug("could not determine content type, setting None")
			ct = None

		# run content-type api additions
		if hasattr(self.obj,'public_api_additions'):
			self.content_type_specific = {}
			for f in self.obj.public_api_additions:
				# name of content_type function: function output
				self.content_type_specific[f.__name__] = f()
		else:
			self.content_type_specific = {}

		# build response
		return {
			'pid': self.obj.pid,
			'content_type': ct,
			'solr_doc': self.obj.SolrDoc.asDictionary(),
			'member_of_collections': {
				'pids':self.obj.isMemberOfCollections
			},
			'learning_objects': self.obj.hasLearningObjects,
			'content_type_specific': self.content_type_specific,
			'matches': getattr(self.obj.SolrDoc.raw, 'matches', None)
		}


	def get_collection_metadata(self):

		'''
		Method to include collection metadata for an item
		'''

		coll_meta_list = {}

		if self.obj.isMemberOfCollections:
			for coll_pid in self.obj.isMemberOfCollections:

				try:
					# open collection obj and append solr doc
					coll_obj = WSUDOR_Object(coll_pid)
					coll_meta_list[coll_obj.pid] = coll_obj.SolrDoc.asDictionary()
				except:
					logging.debug('claims to be part of collection, but could not retrieve collection metadata')

		return coll_meta_list



class ItemMetadata(Item):

	'''
	desc: returns full metadata information for a single item
	expects: PID of item to retrieve
	'''

	def __init__(self, *args, **kwargs):
		self.content_type_specific = {}


	def get(self, pid):

		# init Item
		super( ItemMetadata, self ).__init__(pid)

		# init ResponseObject
		response = ResponseObject()

		# build and respond
		response.status_code = 200

		# build base
		response.body = self.get_item_metadata()

		# include collection metadata
		response.body['member_of_collections']['metadata'] = self.get_collection_metadata()

		# return
		return response.generate_response()


class ItemFile(Item):

	'''
	desc: returns full metadata information for a single item
	expects: PID of item to retrieve
	'''

	def __init__(self, *args, **kwargs):
		pass

	def get(self, pid, datastream):

		# init Item
		super( ItemFile, self ).__init__(pid,skip_load=True)

		# init ResponseObject
		response = ResponseObject()

		# init parser
		parser = reqparse.RequestParser(bundle_errors=True)

		# parse args
		parser.add_argument('key', type=str, help='expecting secret download key', default=False)
		parser.add_argument('token', type=str, help='expecting download one-use token ', default=False)
		parser.add_argument('download', type=flask_restful.inputs.boolean, help='if set, download headers are sent', default=False)
		args = parser.parse_args()

		# init BitStream
		bs = BitStream(pid, datastream, key=args['key'], token=args['token'], download=args['download'], headers=request.headers)
		return bs.stream()


class ItemThumbnail(Item):

	'''
	desc: Return thumbnail for item
	expecting: pid, delivery_mechanism
	'''

	def __init__(self,**kwargs):
		self.delivery_mechanism = kwargs['delivery_mechanism']

	def get(self, pid):

		# init Item
		super( ItemThumbnail, self ).__init__(pid,skip_load=True)

		# init ResponseObject
		response = ResponseObject()

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


class ItemPreview(Item):

	'''
	desc: Return thumbnail for item
	expecting: pid, delivery_mechanism
	'''

	def __init__(self,**kwargs):
		self.delivery_mechanism = kwargs['delivery_mechanism']

	def get(self, pid):

		# init Item
		super( ItemPreview, self ).__init__(pid)

		# get image/loris params from object's preview() method
		loris_args = self.obj.previewImage()
		logging.debug(loris_args)

		# use ItemLoris to return bits
		return ItemLoris().get(*loris_args)


class ItemLoris(Item):

	'''
	desc: Returns datastream via loris	
	'''

	def __init__(self, *args, **kwargs):
		pass

	def get(self, pid, datastream, region=None, size=None, rotation=None, quality=None, format=None):

		# init Item
		super( ItemLoris, self ).__init__(pid, skip_load=True)

		# init ResponseObject
		response = ResponseObject()

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


class ItemIIIF(Item):

	'''
	desc: Returns datastream via loris	
	'''

	def __init__(self, *args, **kwargs):
		pass

	def get(self, pid, annotation_list=False):

		# init Item
		super( ItemIIIF, self ).__init__(pid,skip_load=True)

		# init ResponseObject
		response = ResponseObject()

		if annotation_list:
			return iiif_annotation_list(pid)

		else:
			return iiif_manifest(pid)


class ItemCanvasIIIF(Item):

	'''
	desc: Returns datastream via loris	
	'''

	def __init__(self, *args, **kwargs):
		pass

	def get(self, pid, canvas, annotation_list=False):

		# init Item
		super( ItemCanvasIIIF, self ).__init__(pid,skip_load=True)

		# init ResponseObject
		response = ResponseObject()

		# temp response
		response.body['msg'] = "We are not yet providing dereferencable Canvas URIs."
		response.status_code = 200	
		return response.generate_response()


class ItemHierarchy(Item):

	'''
	desc: JSON response of item hierarchy
	'''

	def __init__(self, *args, **kwargs):
		pass

	def get(self, pid, include_uris=True):

		# init Item
		super( ItemHierarchy, self ).__init__(pid)

		# init ResponseObject
		response = ResponseObject()

		# load hierarchy
		hierarchy = self.obj.object_hierarchy()

		# insert links for each node
		if include_uris:
			for k in hierarchy.keys():
				for o in hierarchy[k]:
					o['uri'] = 'http://%s/%s/item/%s/hierarchy' % (localConfig.APP_HOST, localConfig.WSUDOR_API_PREFIX, o['pid'])
				
		# build and respond
		response.status_code = 200
		response.body = hierarchy
		return response.generate_response()


class ItemAnalysis(Item):

	'''
	desc: return information to support object analysis
	'''

	def __init__(self, *args, **kwargs):
		self.content_type_specific = {}


	def get(self, pid):

		# init Item
		super( ItemAnalysis, self ).__init__(pid)

		# init ResponseObject
		response = ResponseObject()

		# build and respond
		response.status_code = 200

		# build base
		response.body = self.get_item_metadata()

		# add analysis section
		response.body['analysis'] = {}

		# handle ebooks		
		if self.obj.content_type == 'WSUDOR_WSUebook':

			# get raw_text and tei
			raw_text,tei = self.obj.raw_text()

			# prepare tei_as_html
			# replace <lb> with <br>
			tei = tei.replace('<lb/>','<br/>')

			# get page divs
			tei_xml = etree.fromstring(tei)
			nsmap = tei_xml.nsmap.copy()
			try:
				nsmap.pop(None)
			except:
				pass
			page_divs = tei_xml.xpath('//tei:text//tei:div', namespaces=nsmap)

			# loop through
			for page_div in page_divs:

				# get page num
				page_num = int(page_div.attrib['n'])

				# wrap in row
				row = etree.Element('div')
				row.set('class','row')

				# create text div
				text_div = etree.Element('div')
				text_div.set('class','col-md-6')

				# add "see page image" link
				img_link = etree.Element('p')
				img_link.set('class','page_img_link')
				img_link.set('data','%s' % page_num)
				img_link.text = '[see page image]'
				text_div.append(img_link)

				# grab all children and move to text
				children = page_div.getchildren()
				for child in children:
					text_div.append(child)

				# append to page_div
				row.append(text_div)

				# create page image div
				image_div = etree.Element('div')
				image_div.set('class','col-md-6')

				# create image tag
				img = etree.Element('img')
				img.set('id','img_%s' % page_num)
				img.set('data','https://digidev3.library.wayne.edu/loris/fedora:%s_Page_%s|JP2/full/full/0/default.jpg' % (self.obj.pid, page_num))
				img.set('class','page_image')
				image_div.append(img)
				
				# append to pagediv
				row.append(image_div)

				# append row
				page_div.append(row)

				# append <hr>
				hr = etree.Element('hr')
				hr.set('class','hr_page_break')
				page_div.append(hr)

			response.body['analysis']['tei_as_html'] = etree.tostring(tei_xml)

		# return
		return response.generate_response()


# Items - WSUebook
#################################################################################
class ItemWSUebookRawText(Item):

	'''
	desc: Returns raw text from WSUebook
	'''

	def __init__(self, *args, **kwargs):
		pass

	def get(self, pid):		

		# init Item
		super( ItemWSUebookRawText, self ).__init__(pid, skip_load=False)

		# init ResponseObject
		response = ResponseObject()

		# get raw text
		raw_text = self.obj.raw_text()

		# return response
		return Response(raw_text, mimetype='text/plain')


class ItemWSUebookPageRangeRawText(Item):

	'''
	desc: Returns raw text from WSUebook
	'''

	def __init__(self, *args, **kwargs):
		pass

	def get(self, pid, page_range):		

		# init Item
		super( ItemWSUebookPageRangeRawText, self ).__init__(pid, skip_load=False)

		# init ResponseObject
		response = ResponseObject()

		# get page range
		page_range = list(utilities.parseIntSet(nputstr=page_range))

		# get raw text
		raw_text = self.obj.extract_page_range_raw_text(page_range)

		# return response
		return Response(raw_text, mimetype='text/plain')


# Search
#################################################################################
class Search(Resource):

	'''
	Class for capturing request args and setting container for search params
	'''

	def __init__(self):

		# order from https://wiki.apache.org/solr/CommonQueryParameters
		# expose this configuration to localConfig.py?
		self.default_params = { 
			'q': '*:*',
			'sort': None,
			'start': 0,
			'rows': 20,
			'fq': [],
			'fl': [ "id", "mods*", "dc*", "rels*", "human*", "obj*", "last_modified"],
			'facet': True,
			'facet.mincount': 1,
			'facet.limit': 10,
			'facet.field': [
				"rels_hasContentModel",
				"rels_isMemberOfCollection",  	
				"human_hasContentModel",
				"human_isMemberOfCollection",
				"facet_mods_year",
				"dc_subject",
				"dc_creator",
				"dc_coverage",
				"dc_language",
				"dc_publisher",
				"dc_title"
			],
			'facet.sort': 'count', # default facet sorting to count
			'f.facet_mods_year.facet.sort': 'count', # sort mods_year by index (year)
			'wt': 'json',
		}

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

		# query escaping
		# re: https://lucene.apache.org/core/2_9_4/queryparsersyntax.html
		'''
		default behavior is to escape 'q' entirely, and 'fq' only after first, requisite ':'
		however, this can be overridden by the presence of 'field_skip_escape' for specific fields
		'''		
		# escaping 'q'
		if 'q' not in self.field_skip_escape:
			# consider special case for "*" wildcards?
			if self.params['q'] != "*:*":
				self.params['q'] = utilities.escapeSolrArg(self.params['q'])
		if 'fq' not in self.field_skip_escape:
			self.params['fq'] = [ '%s:%s' % ( utilities.escapeSolrArg(value.split(':')[0]), utilities.escapeSolrArg( ':'.join(value.split(':')[1:]) ) ) for value in self.params['fq'] ]

		# flip on facets of fields requested
		if 'facet.field' in self.params and len(self.params['facet.field']) > 0:
			self.params['facet'] = True		

		# limit to isDiscoverable unless overridden
		if self.isDiscoverable:
			logging.debug("limiting to isDiscoverable")
			self.params['fq'].append('rels_isDiscoverable:"info\:fedora/True"')


	def capture_request_args(self):

		# using request arg parsing from flask-restful
		# http://flask-restful-cn.readthedocs.io/en/0.3.5/reqparse.html

		# init parser
		parser = reqparse.RequestParser(bundle_errors=True)

		# parse args

		# solr-based
		parser.add_argument('q', type=str, help='expecting solr search string')
		parser.add_argument('fq', type=str, action='append', help='expecting filter query (fq) (multiple)')
		parser.add_argument('fq[]', type=str, action='append', help='expecting filter query (fq) (multiple) - bracket form')
		parser.add_argument('fl', type=str, action='append', help='expecting field limiter (fl) (multiple)')
		parser.add_argument('facet.field', type=str, action='append', help='expecting field to return as facet (multiple)')
		parser.add_argument('facet.field[]', type=str, action='append', help='expecting field to return as facet (multiple) - bracket form')
		parser.add_argument('facet.limit', type=int, help='expecting integer to limit facet results')
		parser.add_argument('sort', type=str, help='expecting field to sort by') # add multiple for tiered sorting?
		parser.add_argument('rows', type=int, help='expecting integer for number of rows to return')
		parser.add_argument('start', type=int, help='expecting integer for where to start in results')
		parser.add_argument('wt', type=str, help='expecting string for return format (e.g. json, xml, csv)')

		# custom
		parser.add_argument('isDiscoverable', type=flask_restful.inputs.boolean, help='if true, only rels_isDiscoverable:info:fedora/True are returned (default True)', default=True)
		parser.add_argument('skip_defaults', type=flask_restful.inputs.boolean, help='true / false: if set false, will not load default solr params', default=False)
		parser.add_argument('field_skip_escape', type=str, action='append', help='specific solr field to skip escaping on, e.g. "id" or "dc_title" (multiple)', default=[])
		args = parser.parse_args()

		# log incoming API args
		logging.debug("Incoming args from search request:")
		logging.debug(args)

		# set and pop custom fields
		for custom_field in ['skip_defaults','isDiscoverable','field_skip_escape']:
			setattr(self, custom_field, args[custom_field])
			del args[custom_field]

		# remove None values from args
		self.args = dict( (k, v) for k, v in args.iteritems() if v != None )

		# for fields with optional '[]'' suffix, remove
		'''
		Consider removing: with custom query parser on front-end, we can be strict with API
		that it only accepts non-bracketed repeating fields.
		Also, bracketed fields above...
		Or, keep for maximum flexibility, and not that many potential repeating fields
		'''
		for k,v in self.args.iteritems():
			if k.endswith('[]'):
				logging.debug("stripping '[]' suffix from pair: %s / %s" % (k,v))
				self.args[k.rstrip('[]')] = v
				del self.args[k]

		# log post processing
		logging.debug("Post-Processing args from search request:")
		logging.debug(self.args)

		# if q = '', remove, falls back on default "*:*"
		if 'q' in self.args.keys() and self.args['q'] == '':
			del self.args['q']


	def execute_search(self, include_item_metadata=True):
		logging.debug("Merged parameters for search request:")
		logging.debug(self.params)
		self.search_results = solr_handle.search(**self.params)		
		# logging.debug(self.search_results.raw_content)
		# success
		if self.search_results.status == 200:
			if include_item_metadata:
				self.interleave_item_metadata()
			# fix facets
			self.process_facets()
			# check dupe title
			self.check_dupe_title()


	def interleave_item_metadata(self):
		# inteleave single item metadata URLs
		if self.search_results.raw_content['response']['numFound'] > 0:
			for doc in self.search_results.raw_content['response']['docs']:
				doc['item_metadata'] = 'http://%s/%s/item/%s' % (localConfig.APP_HOST, localConfig.WSUDOR_API_PREFIX, doc['id'])


	def process_facets(self):
		'''
		When Solr writes to JSON, it can return a variety of arrangements.  Unfortunately,
		mysolr does not handle the `arrarr` mapping which would be most convenient and align with
		desired use cases on the front-end.

		This shim converts the "flat" style response to a list of tuples, that can be dropped
		into templates and iterated over with ease
		'''
		facet_fields = self.search_results.raw_content['facet_counts']['facet_fields']
		for facet in facet_fields:
			facet_fields[facet] = [tuple(facet_fields[facet][i:i+2]) for i in range(0, len(facet_fields[facet]), 2)]


	def check_dupe_title(self):
		'''
		Some archival materials are ingested with identical titles.
		If the dc_title facet is > 1, we have duplicate titles.
		Perform another quick query, include in API response
		'''
		# dc_title = self.search_results.raw_content['facet_counts']['facet_fields']
		pass



	# generic search GET request
	def get(self):

		# init ResponseObject
		response = ResponseObject()

		# execute query
		self.execute_search()

		# build response
		response.status_code = 200
		response.body = {
			'solr_results': self.search_results.raw_content
		}
		return response.generate_response()


class SearchLimiters(Search):

	'''
	desc: returns limiters for advanced search interfaces
	includes
		- Collections, Content Types
	'''

	def get(self):

		# init ResponseObject
		response = ResponseObject()

		# add collection pid to fq
		self.params = { 
			'q': '*:*',
			'start': 0,
			'rows': 0,
			'fq': [],
			'facet': True,
			'facet.mincount': 1,
			'facet.limit': -1,
			'facet.field': [
				"human_hasContentModel",
				"human_isMemberOfCollection",
				"dc_language"
			],
			'facet.sort': 'index', # default facet sorting to index
			# 'f.facet_mods_year.facet.sort': 'index', # sort mods_year by index (year)
			'wt': 'json',
		}

		# execute query
		self.execute_search()

		# build response
		response.status_code =200
		response.body = {
			'solr_results': self.search_results.raw_content
		}
		return response.generate_response()



# Collections
#################################################################################
class CollectionMetadata(Item):

	'''
	desc: returns full metadata information for collection item
	expects: PID of item to retrieve
	'''

	def __init__(self, *args, **kwargs):
		pass

	def get(self, pid):

		# init Item
		super( CollectionMetadata, self ).__init__(pid)

		# init ResponseObject
		response = ResponseObject()

		# if found, build and respond
		response.status_code = 200
		response.body = self.get_item_metadata()

		# include link for collection search
		response.body['collection_search'] = 'http://%s/%s/collection/%s/search' % (localConfig.APP_HOST, localConfig.WSUDOR_API_PREFIX, pid)

		return response.generate_response()


class Collections(Search):

	'''
	desc: returns information about all collections
	'''

	def get(self):

		# init ResponseObject
		response = ResponseObject()

		# add collection pid to fq
		self.params['fq'] = []
		self.params['fq'].append('rels_hasContentModel:info\:fedora/CM\:Collection')
		self.params['fq'].append('rels_isPrimaryCollection:True')

		# set rows 1000
		self.params['rows'] = 1000

		# sort alphabetically
		self.params['sort'] = 'dc_title_sorting asc'

		# execute query
		self.execute_search()

		# build response
		response.status_code =200
		response.body = {
			'solr_results': self.search_results.raw_content
		}
		return response.generate_response()


class CollectionSearch(Search):

	'''
	desc: collection search class, solr search within a single collection
	expects: collection pid
	'''

	def get(self, pid):

		# init ResponseObject
		response = ResponseObject()

		# get object
		obj = WSUDOR_Object(pid)
		if not obj:
			abort(404, message='%s not found' % pid)

		# add collection pid to fq
		if 'fq' not in self.params:
			self.params['fq'] = []
		self.params['fq'].append('rels_isMemberOfCollection:info\:fedora/%s' % pid.replace(":","\:"))

		# execute query
		self.execute_search()

		# build response
		response.status_code =200
		response.body = {
			'solr_results': self.search_results.raw_content
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


# OAI-PMH
#################################################################################
class OAIServer(Resource):

	def get(self):

		# parse OAI-PMH arguments
		parser = reqparse.RequestParser(bundle_errors=True)
		# oai_verbs = ('GetRecord','Identify','ListIdentifiers','ListMetadataFormats','ListRecords','ListSets')
		# parser.add_argument('verb', type=str, choices=oai_verbs, help='OAI-PMH verb required: %s' % str(oai_verbs))
		parser.add_argument('verb', type=str, help='OAI-PMH verb')
		parser.add_argument('set', type=str, help='OAI-PMH set')
		parser.add_argument('metadataPrefix', type=str, help='OAI-PMH metadataPrefix')
		parser.add_argument('identifier', type=str, help='OAI-PMH identifier')
		parser.add_argument('from', type=str, help='OAI-PMH from')
		parser.add_argument('until', type=str, help='OAI-PMH until')
		parser.add_argument('resumptionToken', type=str, help='OAI-PMH resumptionToken')
		args = parser.parse_args(strict=True)

		# debug
		logging.debug("OAI-PMH request args: %s" % args)

		# if no verb is present, return JSON response
		if not args['verb']:
			logging.debug("no OAI verb present, returning informative JSON response")
			# init ResponseObject
			response = ResponseObject()
			# build response
			response.status_code = 200
			response.body = {
					'help':'Integrated Ouroboros OAI-PMH server.  This server requires, and responds to the standard six OAI-PMH verbs: GetRecord, Identify, ListIdentifiers, ListMetadataFormats, ListRecords, ListSets.  Examples URL patterns are provided in this JSON response.',
					'example_url_patterns':{
						'Identify':'http://%s/api/oai?verb=Identify' % (localConfig.PUBLIC_HOST),
						'ListMetadataFormats':'http://%s/api/oai?verb=ListMetadataFormats' % (localConfig.PUBLIC_HOST),
						'ListIdentifiers':'http://%s/api/oai?verb=ListIdentifiers&metadataPrefix=mods' % (localConfig.PUBLIC_HOST),
						'GetRecord':'http://%s/api/oai?verb=GetRecord&identifier=oai:digital.library.wayne.edu:wayne:vmc14515&metadataPrefix=mods' % (localConfig.PUBLIC_HOST),
						'ListRecords':'http://%s/api/oai?verb=ListRecords&metadataPrefix=mods' % (localConfig.PUBLIC_HOST),
						'ListSets':'http://%s/api/oai?verb=ListSets' % (localConfig.PUBLIC_HOST),
					}
				}
			# return response		
			return response.generate_response()
		
		# init OAIProvider
		op = OAIProvider(args)

		# build and return response
		return Response(op.generate_response(), mimetype="text/xml")

		
