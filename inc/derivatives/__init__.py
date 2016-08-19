# -*- coding: utf-8 -*-

import tempfile

class Derivative(object):

	'''
	General class for creating derivative files.
	This class provides some IO methods for temporary files, input files, output, etc.
	'''

	def __init__(self):
		pass

	def create_temp_file(self):
		return tempfile.NamedTemporaryFile(prefix='ouroboros_', dir='/tmp/Ouroboros/')


