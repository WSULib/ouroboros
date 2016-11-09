# -*- coding: utf-8 -*-
# WSUDOR_API : models.py


# Ouroboros config
import localConfig

# modules
from flask_restful import Resource

# WSUDOR_API_app
from WSUDOR_API import api


class HelloWorld(Resource):
    def get(self):
        return {'hello': 'world'}