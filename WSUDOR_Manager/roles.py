# Ouroboros manager roles

from functools import wraps
from flask import g, request, redirect, url_for

from WSUDOR_Manager import models



class auth(object):

	'''
	This decorator function expects the first and only argument to be a list of roles.
	These roles are checked against the roles of the user.
	'''

	def __init__(self, roles):
		"""
		If there are no decorator arguments, the function
		to be decorated is passed to the constructor.
		"""
		self.roles = roles
		self.roles_string = ",".join(roles)


	def __call__(self, f):
		"""
		The __call__ method is not called until the
		decorated function is called.
		"""
		@wraps(f)
		def wrapped_f(*args, **kwargs):
			print "Authorized roles for this view:", self.roles
			print "User roles:", g.user.roles()

			# authorize
			role_overlap = set(self.roles) & set(g.user.roles())

			if len(role_overlap) > 0:
				print "matched on", role_overlap
				return f(*args, **kwargs)
			else:
				print "did not find role overlap"
				return redirect(url_for('authfail', route_roles=self.roles_string))

		return wrapped_f