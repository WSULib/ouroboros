# -*- coding: utf-8 -*-

import tempfile
from eulfedora.models import XmlDatastreamObject

class Derivative(object):

	'''
	General class for creating derivative files.
	This class provides some IO methods for temporary files, input files, output, etc.
	'''

	def __init__(self):
		pass

	@classmethod
	def create_temp_file(self, file_type='named', suffix=''):
		
		if file_type == 'memory':
			return tempfile.SpooledTemporaryFile(max_size=(1024 * 1024 * 1024), prefix='ouroboros_', dir='/tmp/Ouroboros/')

		else:
			return tempfile.NamedTemporaryFile(prefix='ouroboros_', suffix=suffix, dir='/tmp/Ouroboros/', delete=False)


	@classmethod
	def write_temp_file(self, ds_handle, file_type='named', suffix='' ):

		'''
		expecting datastream "ds_handle" to write to temporary file
		improvement: account for XML datastreams as well
		'''

		if file_type == 'memory':
			f = tempfile.SpooledTemporaryFile(max_size=(1024 * 1024 * 1024), prefix='ouroboros_', dir='/tmp/Ouroboros/')

		else:
			f =  tempfile.NamedTemporaryFile(prefix='ouroboros_', suffix=suffix, dir='/tmp/Ouroboros/', delete=False)

		# write ds_handle to temp file
		# if XmlDatastreamObject, serialize:
		if type(ds_handle) == XmlDatastreamObject:
			f.write(ds_handle.content.serialize())
		# else, write content
		else:
			f.write(ds_handle.content)
		
		f.close()

		# return f
		return f

