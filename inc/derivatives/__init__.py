# -*- coding: utf-8 -*-

import tempfile

class Derivative(object):

	'''
	General class for creating derivative files.
	This class provides some IO methods for temporary files, input files, output, etc.
	'''

	def __init__(self):
		pass

	def create_temp_file(self, file_type='named', suffix=''):
		
		if file_type == 'memory':
			return tempfile.SpooledTemporaryFile(max_size=(1024 * 1024 * 1024), prefix='ouroboros_', dir='/tmp/Ouroboros/')

		else:
			return tempfile.NamedTemporaryFile(prefix='ouroboros_', suffix=suffix, dir='/tmp/Ouroboros/', delete=True)


