# Ouroboros manager roles

from functools import wraps
from flask import g, request, redirect, url_for

from WSUDOR_Manager import models




# administrator role check
def admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):

        # do things here

        return f(*args, **kwargs)

    return decorated_function

# metadata role check
def metadata(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):

        # do things here

        return f(*args, **kwargs)

    return decorated_function

# view role check
def view(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):

        # do things here
        print "checking view auth"
        if 'view' in g.user.roles():
        	return f(*args, **kwargs)
    	else:
    		return redirect(url_for('authfail'))

    return decorated_function