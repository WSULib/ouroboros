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

api_blueprint = Blueprint('api', __name__)
api = Api(api_blueprint)

# IDENTIFY
api.add_resource(models.Identify, '/', endpoint='identify')

# ITEMS
# api.add_resource(models.Item, '/%(API_PREFIX)s/item/<string:pid>' % {'API_PREFIX':API_PREFIX}, endpoint='item')

# # SEARCH
# api.add_resource(models.Search, '/%(API_PREFIX)s/search' % {'API_PREFIX':API_PREFIX}, endpoint='search')
# api.add_resource(models.CollectionSearch, '/%(API_PREFIX)s/collection/<string:pid>/search' % {'API_PREFIX':API_PREFIX}, endpoint='collection_search')

# # TESTING
# api.add_resource(models.HelloWorld, '/%(API_PREFIX)s/hello/<string:name>' % {'API_PREFIX':API_PREFIX}, endpoint='helloworld')
# api.add_resource(models.ArgParsing, '/%(API_PREFIX)s/goober' % {'API_PREFIX':API_PREFIX}, endpoint='goober_integrity')


















