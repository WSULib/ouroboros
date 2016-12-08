# -*- coding: utf-8 -*-
# WSUDOR_API : views.py

# Ouroboros config
import localConfig

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

# IDENTIFY
api.add_resource(models.Identify, '/', endpoint='identify')

# ITEMS
api.add_resource(models.ItemMetadata, '/item/<string:pid>', endpoint='item_metadata') # single item page
api.add_resource(models.ItemFile, '/item/<string:pid>/file/<string:datastream>', endpoint='item_file') # datastream fom single item, via bitStream

# SEARCH
api.add_resource(models.Search, '/search', endpoint='search')
api.add_resource(models.CollectionSearch, '/collection/<string:pid>/search', endpoint='collection_search')

# TESTING
api.add_resource(models.HelloWorld, '/hello/<string:name>', endpoint='helloworld')
api.add_resource(models.ArgParsing, '/goober', endpoint='goober_integrity')


















