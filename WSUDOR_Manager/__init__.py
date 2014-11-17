# root file, app instantiator

# modules / packages import
from flask import Flask, render_template, g
from flask.ext.sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine, MetaData
from flask.ext.login import LoginManager

# import WSUDOR ContentTypes
import WSUDOR_ContentTypes

# create app
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://WSUDOR_Manager:WSUDOR_Manager@localhost/WSUDOR_Manager'
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

# get handlers
import views






