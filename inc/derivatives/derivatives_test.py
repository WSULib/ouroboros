# -*- coding: utf-8 -*-

'''
This should be run from the root Ouroboros directory: py.test --verbose
'''

import os
import pytest

# init derivative instance
from __init__ import Derivative
def test_deriv_init():
	deriv = Derivative()
	assert type(deriv) == Derivative
	return deriv

deriv = test_deriv_init()


############################################
# BASE DERIVATIVE CLASS
############################################
class TestDerivativeClass:

	# create temporary file and assert existence
	def test_derive_temp_file(self):
		deriv_temp_file = deriv.create_temp_file()
		assert os.path.exists(deriv_temp_file.name)


############################################
# IMAGE
############################################
from image import ImageDerivative

class TestImageClass():

	def test_image_deriv_init(self):
		image_deriv = ImageDerivative()
		assert type(image_deriv) == ImageDerivative







