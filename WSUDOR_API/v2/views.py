# -*- coding: utf-8 -*-
# WSUDOR_API : views.py

# Ouroboros config
import localConfig

# Logging
from WSUDOR_API import logging

# WSUDOR_API_app
# from WSUDOR_API import api
import models

# Flask
from flask import Blueprint
from flask_restful import Api

# register blueprint
api_blueprint = Blueprint('api', __name__)

# init flask-restful api handle
api = Api(api_blueprint)

# General
api.add_resource(models.Identify, '/', endpoint='identify')

# Items
api.add_resource(models.ItemMetadata, '/item/<string:pid>', endpoint='item_metadata') # single item page
api.add_resource(models.ItemFile, '/item/<string:pid>/file/<string:datastream>', endpoint='item_file') # datastream fom single item, via bitStream
api.add_resource(models.ItemThumbnail, '/item/<string:pid>/thumbnail', endpoint='item_thumbnail', resource_class_kwargs={'delivery_mechanism':'loris'}) # single item thumbnail, choose either 'bitStream' or 'loris' for 'delivery_mechanism'
api.add_resource(models.ItemPreview, '/item/<string:pid>/preview', endpoint='item_preview', resource_class_kwargs={'delivery_mechanism':'loris'}) # single item thumbnail, choose either 'bitStream' or 'loris' for 'delivery_mechanism'
api.add_resource(models.ItemLoris, '/item/<string:pid>/loris/<string:datastream>/<string:region>/<string:size>/<int:rotation>/<string:quality>.<string:format>', endpoint='item_loris_image') # returns item datastream via Loris
api.add_resource(models.ItemLoris, '/item/<string:pid>/loris/<string:datastream>/info.json', endpoint='item_loris_json') # returns item datastream via Loris
api.add_resource(models.ItemIIIF, '/item/<string:pid>/iiif', endpoint='item_iiif') # iiif manifest for item
api.add_resource(models.ItemIIIF, '/item/<string:pid>/iiif/manifest.json', endpoint='item_iiif_manifest') # iiif manifest for item
api.add_resource(models.ItemCanvasIIIF, '/item/<string:pid>/iiif/canvas/<string:canvas>.json', endpoint='canvas_iiif_manifest') # iiif manifest for item
api.add_resource(models.ItemIIIF, '/item/<string:pid>/iiif/annotation_list', endpoint='item_iiif_annotation_list', defaults={'annotation_list': True}) # iiif annotation list for item
api.add_resource(models.ItemHierarchy, '/item/<string:pid>/hierarchy', endpoint='item_hierarchy', defaults={'include_uris': True}) # return object hierarchy
api.add_resource(models.ItemAnalysis, '/item/<string:pid>/analysis', endpoint='item_analysis') # API response to support item analysis

# Content-Type Specific
# WSUebooks
api.add_resource(models.ItemWSUebookRawText, '/item/<string:pid>/text/<string:raw_text_type>', endpoint='wsuebook_raw_text') # raw text from wsuebook

# Collection
api.add_resource(models.Collections, '/collections', endpoint='collections')
api.add_resource(models.CollectionMetadata, '/collection/<string:pid>', endpoint='collection_metadata') # collection metadata∞
api.add_resource(models.CollectionSearch, '/collection/<string:pid>/search', endpoint='collection_search')

# Search
api.add_resource(models.Search, '/search', endpoint='search')
api.add_resource(models.Search, '/WSUAPI', endpoint='v1_search')
api.add_resource(models.SearchLimiters, '/search_limiters', endpoint='search_limiters')

# Users
api.add_resource(models.UserWhoami, '/user/<string:username>/whoami', endpoint='user_whoami')

# Integrated OAI-PMH server
api.add_resource(models.OAIServer, '/oai', endpoint='oai')




















