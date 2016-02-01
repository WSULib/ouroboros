# root file, app instantiator
import os

# modules / packages import
from flask import Flask, render_template, g
from flask.ext.sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine, MetaData
from flask.ext.login import LoginManager
import localConfig

# create app
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://%s:%s@localhost/%s' % (localConfig.MYSQL_USERNAME, localConfig.MYSQL_PASSWORD, localConfig.MYSQL_DATABASE ) 
# app.config['LOG_REQUESTS'] = True
# app.debug = True

#setup db
db = SQLAlchemy(app)
engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'], convert_unicode=True)
metadata = MetaData(bind=engine)
db_con = engine.connect()

# start up login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# import WSUDOR ContentTypes
import WSUDOR_ContentTypes
from WSUDOR_ContentTypes import *

# get handlers
import views

# generate required folders if not present
if not os.path.exists('/tmp/Ouroboros'):
	os.mkdir('/tmp/Ouroboros')
if not os.path.exists('/tmp/Ouroboros/ingest_workspace'):
	os.mkdir('/tmp/Ouroboros/ingest_workspace')






