from flask import Flask, url_for
from werkzeug.serving import run_simple
from werkzeug.wsgi import DispatcherMiddleware

from fedoraManager2 import app as fm2_app
 
wrapper_app = Flask(__name__) 

wrapper_app = DispatcherMiddleware(wrapper_app, {"/fedoraManager2-graham": fm2_app})
 
if __name__ == "__main__":
    run_simple('digital.library.wayne.edu', 5001, wrapper_app)




