# root file, app instantiator

# modules / packages import
from flask import Flask, render_template, g
from flask.ext.login import LoginManager

# create app
WSUAPI_app = Flask(__name__)
WSUAPI_app.debug = True

# start up login (keep for session dev)
# login_manager = LoginManager()
# login_manager.init_app(app)
# login_manager.login_view = 'login'

# get handlers
import views