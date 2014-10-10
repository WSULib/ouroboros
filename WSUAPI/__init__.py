# root file, app instantiator

# modules / packages import
from flask import Flask, render_template, g
from flask.ext.login import LoginManager

# create app
WSUAPI_app = Flask(__name__)
WSUAPI_app.debug = True

# get handlers
import views