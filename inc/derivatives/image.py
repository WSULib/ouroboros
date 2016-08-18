# -*- coding: utf-8 -*-

# import os
# import subprocess
# from datetime import datetime
# import uuid

from inc.derivatives import Derivative

class ImageDerivative(Derivative):

	'''
	Extends Derivative to create image derivatives such as thumbnails and JPEG2000s.
	'''

	def __init__(self):
		pass


	def makeJP2(self):
		pass












# # utility for making derivatives

# '''
# Repurposed from Princeton's JP2 "recipes" shared with us from Princeton:
# https://github.com/pulibrary/jp2_derivatives/blob/master/mkderiv.py.tmpl
# '''



# KDU_RECIPE_KEY = '10_1' # '10_1','20_1','lossless'
# IMAGEMAGICK_SIZE_KEY = 'full' # "full" or "3600"
# OVERWRITE_EXISTING = False
# THREADS = '4'
# LOG_TO = 'console' # "console" or "file"
# EXIV2 = "/usr/bin/exiv2"
# CONVERT = "/usr/bin/convert"
# KDU_COMPRESS_DIR = "/usr/local/bin"
# KDU_LIB_DIR = "/usr/local/lib"

# # bit modes
# FORTY_EIGHT_BITS = "16 16 16"
# THIRTY_TWO_BITS = "8 8 8 8"
# TWENTY_FOUR_BITS = "8 8 8"
# SIXTEEN_BITS = "16"
# EIGHT_BITS = "8"
# ONE_BIT = "1"

# IMAGEMAGICK_RECIPES = {}
# if IMAGEMAGICK_SIZE_KEY == 'full':
# 	IMAGEMAGICK_RECIPES['color'] = " -quality 100" 
# 	IMAGEMAGICK_RECIPES['gray'] = " -colorspace Gray -quality 100"
# else:
# 	IMAGEMAGICK_RECIPES['color'] = " -resize 3600x3600\> -quality 100"
# 	IMAGEMAGICK_RECIPES['gray'] = " -resize 3600x3600\> -quality 100 -colorspace Gray"

# KDU_RECIPES = {

# 	'10_1_gray' : "\
# -rate 2.4,1.48331273,.91673033,.56657224,.35016049,.21641118,.13374944,.08266171 \
#  Creversible=yes Clevels=7 Cblk=\{64,64\} \
#  -jp2_space sLUM \
#  Cuse_sop=yes Cuse_eph=yes Corder=RLCP ORGgen_plt=yes ORGtparts=R \
#  Stiles=\{256,256\} \
# -double_buffering 10 \
# -num_threads %s \
# -no_weights \
# -quiet" % (THREADS,),

# 	'10_1_color' : "\
# -rate 2.4,1.48331273,.91673033,.56657224,.35016049,.21641118,.13374944,.08266171 \
#  Creversible=yes Clevels=7 Cblk=\{64,64\} \
#  -jp2_space sRGB \
#  Cuse_sop=yes Cuse_eph=yes Corder=RLCP ORGgen_plt=yes ORGtparts=R \
#  Stiles=\{256,256\} \
# -double_buffering 10 \
# -num_threads %s \
# -no_weights" % (THREADS,),

# 	'20_1_gray': "\
# -rate 1.2,0.7416334477,0.4583546103,0.2832827752,0.1750776907,0.1082041271,0.0668737897,0.0413302129 \
#  Creversible=yes Clevels=7 Cblk=\{64,64\} \
# -jp2_space sLUM \
#  Cuse_sop=yes Cuse_eph=yes Corder=RLCP ORGgen_plt=yes ORGtparts=R \
#  Stiles=\{256,256\} \
# -double_buffering 10 \
# -num_threads %s \
# -no_weights \
# -quiet" % (THREADS,),

# 	'20_1_color': "\
# -rate 1.2,0.7416334477,0.4583546103,0.2832827752,0.1750776907,0.1082041271,0.0668737897,0.0413302129 \
#  Creversible=yes Clevels=7 Cblk=\{64,64\} \
# -jp2_space sRGB \
#  Cuse_sop=yes Cuse_eph=yes Corder=RLCP ORGgen_plt=yes ORGtparts=R \
#  Stiles=\{256,256\} \
# -double_buffering 10 \
# -num_threads %s \
# -no_weights \
# -quiet" % (THREADS,),

# 	'lossless_gray' : "\
# -rate -,2.4,1.48331273,.91673033,.56657224,.35016049,.21641118,.13374944,.08266171 \
#  Creversible=yes Clevels=7 Cblk=\{64,64\} \
#  -jp2_space sLUM \
#  Cuse_sop=yes Cuse_eph=yes Corder=RLCP ORGgen_plt=yes ORGtparts=R \
#  Stiles=\{256,256\} \
# -double_buffering 10 \
# -num_threads %s \
# -no_weights \
# -quiet" % (THREADS,),

# 	'lossless_color' : "\
# -rate -,2.4,1.48331273,.91673033,.56657224,.35016049,.21641118,.13374944,.08266171 \
#  Creversible=yes Clevels=7 Cblk=\{64,64\} \
#  -jp2_space sRGB \
#  Cuse_sop=yes Cuse_eph=yes Corder=RLCP ORGgen_plt=yes ORGtparts=R \
#  Stiles=\{256,256\} \
# -double_buffering 10 \
# -num_threads %s \
# -no_weights \
# -quiet" % (THREADS,)


# }

# # will most likely fail on PNGs
# EXIV2_GET_BPS = "-Pt -g Exif.Image.BitsPerSample print"


# # class for making JP2 derivatives
# class JP2DerivativeMaker(object):

# 	'''
# 	expecting:
# 		inPath = input file, probably tiff
# 		outPath = output file, JP2
# 	'''

# 	# init with fhand default to None
# 	def __init__(self, inPath=None, outPath="/tmp/Ouroboros/"+str(uuid.uuid4())+".jp2", inObj=None):
# 		self.inPath = inPath
# 		self.outPath = outPath
# 		self.inObj = inObj


# 	# get bits per sample
# 	def getBitsPerSample(self):
# 		cmd = EXIV2 + " " + EXIV2_GET_BPS + " " + self.inPath
# 		proc = subprocess.Popen(cmd, shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
		
# 		# wait
# 		return_code = proc.wait()
		
# 		# Read from pipes
# 		response = None
# 		for line in proc.stdout:
# 			if response == None:
# 				response = line.rstrip()
# 		for line in proc.stderr:
# 			print(line.rstrip() + " (" + self.inPath + ")") 
			
# 		return response


# 	# gen JP2 and return path of temp file or fhand_out
# 	def makeJP2(self):

# 		inBitsPerSample = self.getBitsPerSample()
# 		print "generating JP2 with BPS:",inBitsPerSample

# 		cmd = "kdu_compress -i " + self.inPath + " -o " + self.outPath 
# 		if inBitsPerSample == FORTY_EIGHT_BITS:
# 			cmd = cmd + " " + KDU_RECIPES[KDU_RECIPE_KEY+'_color']
# 		elif inBitsPerSample == THIRTY_TWO_BITS:
# 			cmd = cmd + " " + KDU_RECIPES[KDU_RECIPE_KEY+'_color']
# 		elif inBitsPerSample == TWENTY_FOUR_BITS:
# 			cmd = cmd + " " + KDU_RECIPES[KDU_RECIPE_KEY+'_color']
# 		elif inBitsPerSample == SIXTEEN_BITS:
# 			cmd = cmd + " " + KDU_RECIPES[KDU_RECIPE_KEY+'_gray']
# 		elif inBitsPerSample == EIGHT_BITS:
# 			cmd = cmd + " " + KDU_RECIPES[KDU_RECIPE_KEY+'_gray']
# 		elif inBitsPerSample == ONE_BIT:
# 			cmd = cmd + " " + KDU_RECIPES[KDU_RECIPE_KEY+'_gray']
# 		else:
# 			print "Could not get bits per sample: " + self.outPath			
# 			return False

# 		print "Issuing Kakadu command",cmd
# 		proc = subprocess.Popen(cmd, shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
# 		return_code = proc.wait()
			
# 		if os.path.exists(self.outPath) and os.path.getsize(self.outPath) != 0:			
# 			print("Created: " + self.outPath)
# 			os.chmod(self.outPath, 0644)
# 			return True
# 		else:
# 			if os.path.exists(self.outPath): os.remove(self.outPath)
# 			print("Failed to create: " + self.outPath)
# 			return False


# 	# small function to write input obj and ds to temp file, returns path
# 	def writeTempOrig(self, ds_handle):		

# 		# get tempfile
# 		temp_filename = "/tmp/Ouroboros/"+str(uuid.uuid4())+".tif"
		
# 		with open(temp_filename,'wb') as fhand:
# 			# write to tempfile
# 			fhand.write(ds_handle.content)

# 		return temp_filename


# 	def cleanupTempFiles(self):

# 		# remove temp outPath
# 		try:
# 			os.remove(self.outPath)
# 			print "removed",self.outPath
# 		except:
# 			print "could not remove / find",self.outPath


# 	def uncompressOriginal(self):
# 		print "Converting temp tiff to uncompressed"
# 		cmd = "convert -verbose %s +compress %s" % (self.inPath, self.inPath)
# 		proc = subprocess.Popen(cmd, shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
# 		return_code = proc.wait()
# 		return True


# 	def createTiffFromOriginal(self):
# 		print "creating tiff from original image file"
# 		cmd = "convert -verbose %s +compress %s.tif" % (self.inPath, self.inPath)
# 		proc = subprocess.Popen(cmd, shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
# 		return_code = proc.wait()
# 		return True






































