# -*- coding: utf-8 -*-

from datetime import datetime
import logging
logging.basicConfig(level=logging.DEBUG)
import os
import subprocess
import time

from inc.derivatives import Derivative


# '''
# Values repurposed from Princeton's kindly shared JP2 "recipes":
# https://github.com/pulibrary/jp2_derivatives/blob/master/mkderiv.py.tmpl
# '''

KDU_RECIPE_KEY = '10_1' # '10_1','20_1','lossless'
IMAGEMAGICK_SIZE_KEY = 'full' # "full" or "3600"
OVERWRITE_EXISTING = False
THREADS = '4'
LOG_TO = 'console' # "console" or "file"
EXIV2 = "/usr/bin/exiv2"
CONVERT = "/usr/bin/convert"
KDU_COMPRESS_DIR = "/usr/local/bin"
KDU_LIB_DIR = "/usr/local/lib"

# bit modes
FORTY_EIGHT_BITS = "16 16 16"
THIRTY_TWO_BITS = "8 8 8 8"
TWENTY_FOUR_BITS = "8 8 8"
SIXTEEN_BITS = "16"
EIGHT_BITS = "8"
ONE_BIT = "1"

IMAGEMAGICK_RECIPES = {}
if IMAGEMAGICK_SIZE_KEY == 'full':
	IMAGEMAGICK_RECIPES['color'] = " -quality 100" 
	IMAGEMAGICK_RECIPES['gray'] = " -colorspace Gray -quality 100"
else:
	IMAGEMAGICK_RECIPES['color'] = " -resize 3600x3600\> -quality 100"
	IMAGEMAGICK_RECIPES['gray'] = " -resize 3600x3600\> -quality 100 -colorspace Gray"

KDU_RECIPES = {

	'10_1_gray' : "\
-rate 2.4,1.48331273,.91673033,.56657224,.35016049,.21641118,.13374944,.08266171 \
 Creversible=yes Clevels=7 Cblk=\{64,64\} \
 -jp2_space sLUM \
 Cuse_sop=yes Cuse_eph=yes Corder=RLCP ORGgen_plt=yes ORGtparts=R \
 Stiles=\{256,256\} \
-double_buffering 10 \
-num_threads %s \
-no_weights" % (THREADS,),

	'10_1_color' : "\
-rate 2.4,1.48331273,.91673033,.56657224,.35016049,.21641118,.13374944,.08266171 \
 Creversible=yes Clevels=7 Cblk=\{64,64\} \
 -jp2_space sRGB \
 Cuse_sop=yes Cuse_eph=yes Corder=RLCP ORGgen_plt=yes ORGtparts=R \
 Stiles=\{256,256\} \
-double_buffering 10 \
-num_threads %s \
-no_weights" % (THREADS,),

	'20_1_gray': "\
-rate 1.2,0.7416334477,0.4583546103,0.2832827752,0.1750776907,0.1082041271,0.0668737897,0.0413302129 \
 Creversible=yes Clevels=7 Cblk=\{64,64\} \
-jp2_space sLUM \
 Cuse_sop=yes Cuse_eph=yes Corder=RLCP ORGgen_plt=yes ORGtparts=R \
 Stiles=\{256,256\} \
-double_buffering 10 \
-num_threads %s \
-no_weights \
-quiet" % (THREADS,),

	'20_1_color': "\
-rate 1.2,0.7416334477,0.4583546103,0.2832827752,0.1750776907,0.1082041271,0.0668737897,0.0413302129 \
 Creversible=yes Clevels=7 Cblk=\{64,64\} \
-jp2_space sRGB \
 Cuse_sop=yes Cuse_eph=yes Corder=RLCP ORGgen_plt=yes ORGtparts=R \
 Stiles=\{256,256\} \
-double_buffering 10 \
-num_threads %s \
-no_weights \
-quiet" % (THREADS,),

	'lossless_gray' : "\
-rate -,2.4,1.48331273,.91673033,.56657224,.35016049,.21641118,.13374944,.08266171 \
 Creversible=yes Clevels=7 Cblk=\{64,64\} \
 -jp2_space sLUM \
 Cuse_sop=yes Cuse_eph=yes Corder=RLCP ORGgen_plt=yes ORGtparts=R \
 Stiles=\{256,256\} \
-double_buffering 10 \
-num_threads %s \
-no_weights \
-quiet" % (THREADS,),

	'lossless_color' : "\
-rate -,2.4,1.48331273,.91673033,.56657224,.35016049,.21641118,.13374944,.08266171 \
 Creversible=yes Clevels=7 Cblk=\{64,64\} \
 -jp2_space sRGB \
 Cuse_sop=yes Cuse_eph=yes Corder=RLCP ORGgen_plt=yes ORGtparts=R \
 Stiles=\{256,256\} \
-double_buffering 10 \
-num_threads %s \
-no_weights \
-quiet" % (THREADS,)


}

# will most likely fail on PNGs
EXIV2_GET_BPS = "-Pt -g Exif.Image.BitsPerSample print"


class ImageDerivative(Derivative):

	'''
	Extends Derivative to create image derivatives such as thumbnails and JPEG2000s.
	'''

	def __init__(self, input_handle, input_type='file'):
		
		# input: filename (future: variable in memory)
		self.input_handle = input_handle

		# output: most likely filename (future: variable in memory)
		self.output_handle = None

		# current state of derivation
		self.state = None

		# next iteration to run
		self.next_iteration = self.uncompressOriginal

		# JP2 color space
		self.jp2_space = None

		# Bit per Sample
		self.BPS = None
		


	# get bits per sample
	def getBitsPerSample(self):
		logging.info("determining Bits per Sample (BPS)")
		cmd = EXIV2 + " " + EXIV2_GET_BPS + " " + self.input_handle
		proc = subprocess.Popen(cmd, shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
		
		# wait
		return_code = proc.wait()
		
		# Read from pipes
		response = None
		for line in proc.stdout:
			if response == None:
				response = line.rstrip()
		for line in proc.stderr:
			print(line.rstrip() + " (" + self.input_handle + ")") 

		logging.debug("BPS: %s" % response)		
		if not response:
			return "Unknown"	
		self.BPS = response
		return self.BPS


	# gen JP2 and return path of temp file or fhand_out
	def makeJP2(self):

		'''
		Loop for creating JP2, with trying derivations of the original input file if 
		not successful the first time.

		param: next_iteration() is the next Image method to run if failed.  For example,
		it defaults to 'self.uncompressOriginal' if not successful the first time.  That creates
		a new tiff file and retries this makeJP2() function, with a *new* next_iteration to try.
		'''

		# instantiates temporary file from Derivative parent class
		self.output_handle = self.create_temp_file(file_type='named', suffix='.jp2')

		inBitsPerSample = self.getBitsPerSample()
		logging.info("generating JP2 with BPS: %s" % inBitsPerSample)

		cmd = "kdu_compress -i " + self.input_handle + " -o " + self.output_handle.name 
		if inBitsPerSample == FORTY_EIGHT_BITS:
			cmd = cmd + " " + KDU_RECIPES[KDU_RECIPE_KEY+'_color']
		elif inBitsPerSample == THIRTY_TWO_BITS:
			cmd = cmd + " " + KDU_RECIPES[KDU_RECIPE_KEY+'_color']
		elif inBitsPerSample == TWENTY_FOUR_BITS:
			cmd = cmd + " " + KDU_RECIPES[KDU_RECIPE_KEY+'_color']
		elif inBitsPerSample == SIXTEEN_BITS:
			cmd = cmd + " " + KDU_RECIPES[KDU_RECIPE_KEY+'_gray']
		elif inBitsPerSample == EIGHT_BITS:
			cmd = cmd + " " + KDU_RECIPES[KDU_RECIPE_KEY+'_gray']
		elif inBitsPerSample == ONE_BIT:
			cmd = cmd + " " + KDU_RECIPES[KDU_RECIPE_KEY+'_gray']
		else:
			logging.warning("Could not find JP2 recipe for %s" + inBitsPerSample)
			return False

		# if color space as part of object, update kakadu command
		if self.jp2_space == 'sRGB':
			cmd = cmd.replace("-jp2_space sLUM","-jp2_space sRGB")
		if self.jp2_space == 'sLUM':
			cmd = cmd.replace("-jp2_space sRGB","-jp2_space sLUM")

		logging.info("firing Kakadu")
		logging.debug(cmd)

		proc = subprocess.Popen(cmd, shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
		return_code = proc.wait()
			
		if os.path.exists(self.output_handle.name) and os.path.getsize(self.output_handle.name) != 0:			
			logging.info("Created: %s" % self.output_handle.name)
			os.chmod(self.output_handle.name, 0644)
			return True
		else:
			if os.path.exists(self.output_handle.name): os.remove(self.output_handle.name)
			logging.info("Failed to create: %s" % self.output_handle.name)
			# retrying
			if self.next_iteration:
				logging.debug("trying next iteration...")
				time.sleep(2)
				self.next_iteration()
			else:
				logging.info('out of input file tries...aborting')
				return False
		

	'''
	Work for tomm - test with files that are fixed by one of these....
	'''


	def uncompressOriginal(self):
		logging.debug("Converting temp tiff to uncompressed")
		new_input_handle = self.create_temp_file(file_type='named', suffix='.tif')
		cmd = "convert -verbose %s +compress %s" % (self.input_handle, new_input_handle.name)
		proc = subprocess.Popen(cmd, shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
		return_code = proc.wait()
		
		# re-run makeJP2 with new input_data
		self.input_handle = new_input_handle.name
		self.next_iteration = self.createTiffFromOriginal
		self.makeJP2()


	def createTiffFromOriginal(self):
		logging.debug("creating tiff from original image file")
		new_input_handle = self.create_temp_file(file_type='named', suffix='.tif')
		cmd = "convert -verbose %s +compress %s" % (self.input_handle, new_input_handle.name)
		proc = subprocess.Popen(cmd, shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
		return_code = proc.wait()
		
		# re-run makeJP2 with new input_data
		self.input_handle = new_input_handle.name
		self.next_iteration = self.newColorSpace
		self.makeJP2()

	def newColorSpace(self):
		logging.debug("trying new jp2 color space for kakadu")
		
		if self.BPS in [ONE_BIT, EIGHT_BITS, SIXTEEN_BITS]:
			self.jp2_space = 'sRGB'

		# re-run makeJP2 with new input_data
		self.next_iteration = None
		self.makeJP2()













































