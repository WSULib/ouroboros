# root file, app instantiator

# modules / packages import
from flask import Flask, render_template, g
from flask.ext.login import LoginManager
from flask.ext.cache import Cache

# create app
WSUDOR_API_app = Flask(__name__)
WSUDOR_API_app.debug = True

# Flask-Cache for API
cache = Cache(WSUDOR_API_app, config={'CACHE_TYPE': 'simple'})

# get handlers
import views
import iiif_manifest
import imageServer