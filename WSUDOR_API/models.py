# -*- coding: utf-8 -*-
# WSUDOR_API : models.py


# Ouroboros config
import localConfig

# modules
from flask_restful import reqparse, Resource

# WSUDOR_API_app
from WSUDOR_API import api

#################################################################################
# TESTING
#################################################################################
class HelloWorld(Resource):

    def get(self, name):
        return {'hello': name}


class ArgParsing(Resource):


	def get(self):
		parser = reqparse.RequestParser()
		parser.add_argument('goober', type=int, help='the particular integrity of goober')
		parser.add_argument('tronic', type=str, help='pecularities of tronic')
		args = parser.parse_args(strict=True)

		'''
		If it 'goober' fails the type=int restriction above, it aborts here and returns a 400 with message = help from above
		if include strict=True in parser.parse_args, squawks if anything but 'goober' or 'tronic' in GET/POST params
		'''

		return {
			'goober_integrity': args['goober'],
			'pecularities_of_tronic': args['tronic']
		}