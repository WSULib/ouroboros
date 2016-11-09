# -*- coding: utf-8 -*-
# WSUDOR_API : models.py


# Ouroboros config
import localConfig

# modules
from flask_restful import abort, fields, reqparse, Resource

# WSUDOR_API_app
from WSUDOR_API import api

#################################################################################
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