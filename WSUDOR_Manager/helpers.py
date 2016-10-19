# Helper Classes and Functions for Ouroboros

import time

from flask import after_this_request, request
from cStringIO import StringIO as IO
import gzip
import functools 


# LazyProperty Decorator
class LazyProperty(object):
	'''
	meant to be used for lazy evaluation of an object attribute.
	property should represent non-mutable data, as it replaces itself.
	'''

	def __init__(self,fget):
		self.fget = fget
		self.func_name = fget.__name__


	def __get__(self,obj,cls):
		if obj is None:
			return None
		value = self.fget(obj)
		setattr(obj,self.func_name,value)
		return value


# generic, empty object class
class BlankObject(object):
	pass


# small decorator to time functions
def timing(f):
	def wrap(*args):
		time1 = time.time()
		ret = f(*args)
		time2 = time.time()
		print '%s function took %0.3f ms, %0.3f s' % (f.func_name, (time2-time1)*1000.0, (time2-time1))
		return ret
	return wrap



def gzipped(f):
	@functools.wraps(f)
	def view_func(*args, **kwargs):
		@after_this_request
		def zipper(response):
			accept_encoding = request.headers.get('Accept-Encoding', '')

			if 'gzip' not in accept_encoding.lower():
				return response

			response.direct_passthrough = False

			if (response.status_code < 200 or
				response.status_code >= 300 or
				'Content-Encoding' in response.headers):
				return response
			gzip_buffer = IO()
			gzip_file = gzip.GzipFile(mode='wb', 
									  fileobj=gzip_buffer)
			gzip_file.write(response.data)
			gzip_file.close()

			response.data = gzip_buffer.getvalue()
			response.headers['Content-Encoding'] = 'gzip'
			response.headers['Vary'] = 'Accept-Encoding'
			response.headers['Content-Length'] = len(response.data)

			return response

		return f(*args, **kwargs)

	return view_func