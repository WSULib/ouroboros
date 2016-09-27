# Ouroboros manager roles

from flask import g, request, redirect, url_for
from functools import wraps
import json

from WSUDOR_Manager import models


class auth(object):

	'''
	This decorator function expects the first and only argument to be a list of roles.
	These roles are checked against the roles of the user.
	'''

	def __init__(self, task_roles, is_celery=False):
		"""
		If there are no decorator arguments, the function
		to be decorated is passed to the constructor.
		"""
		self.task_roles = task_roles
		self.task_roles_string = ",".join(task_roles)
		self.user_roles = []
		self.is_celery = is_celery


	def __call__(self, f):
		"""
		The __call__ method is not called until the
		decorated function is called.
		"""
		@wraps(f)
		def wrapped_f(*args, **kwargs):
			print "Authorized roles for this view:", self.task_roles

			# if celery context, grab user from job_package and query db
			if self.is_celery:
				username = args[0]['username']
				print "celery task initiated by: %s" % username
				user = models.User.get(username)
				self.user_roles = user.roles()
				print "User roles:", self.user_roles

			# if request context, grab roles from g.user
			if not self.is_celery:
				self.user_roles = g.user.roles()
				print "User roles:", self.user_roles

			# if admin, always auth
			if 'admin' in self.user_roles:
				print "user is admin, authorized"
				return f(*args, **kwargs)

			# authorize
			role_overlap = set(self.task_roles) & set(self.user_roles)
			if len(role_overlap) > 0:
				print "matched on", role_overlap
				return f(*args, **kwargs)
			else:
				print "did not find role overlap"
				if not self.is_celery:
					return redirect(url_for('authfail', route_roles=self.task_roles_string))
				if self.is_celery:
					return json.dumps({
								'msg':'your roles do not permit you to perform this task',
								'task_roles':self.task_roles,
								'user_roles':self.user_roles
							})

		return wrapped_f