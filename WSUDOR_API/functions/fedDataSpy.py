import hashlib
import urllib
import sys
import os
import json
import mimetypes

# modules from WSUDOR_Manager
from WSUDOR_Manager.fedoraHandles import fedora_handle


def checkSymlink(PID,DS):
	
	'''
	DEPRECATED, BEGIN USING makeSymLink() below, which pushes symlinks to /var/www/wsuls/symLinks
	'''

	pass

	# returnDict = {}

	# filename = "info:fedora/"+PID+"/"+DS+"/"+DS+".0"
	
	# # get hash folder	
	# hashed_filename = hashlib.md5(urllib.unquote(filename))
	# print "What you seek is in folder:",hashed_filename.hexdigest()[0:2]
	# dataFolder = hashed_filename.hexdigest()[0:2]

	# filename_quoted = urllib.quote_plus(filename)	
	# # peculiars for Fedora
	# ####################################################
	# filename_quoted = filename_quoted.replace('_','%5F')
	# ####################################################

	# # symlink
	# path_prefix = "/var/www/wsuls/iipsrv/"	
	# # jp2
	# file_path = path_prefix+hashed_filename.hexdigest()+".jp2" 	
	
	# returnDict['jp2_symlink'] = file_path;	

	# # exists
	# if os.path.exists(file_path):
	# 	print "Datastream symlink found. Returning file_path."
	# 	return returnDict
	# # create
	# else:				
	# 	source_prefix = "/usr/local/fedora/data/datastreamStore/"
	# 	source_path = source_prefix+dataFolder+"/"+filename_quoted
	# 	print "Looking for this:",source_path

	# 	if os.path.exists(source_path):
	# 		os.symlink(source_path, file_path)
	# 		print "Datastream symlink created.  Returning file_path."
	# 		return returnDict
	# 	else:
	# 		print "Target Not Found."
	# 		return "Target not found.  Aborting."


def makeSymLink(PID, DS):

	returnDict = {}

	filename = "info:fedora/"+PID+"/"+DS+"/"+DS+".0"
	
	# get hash folder	
	hashed_filename = hashlib.md5(urllib.unquote(filename))
	dataFolder = hashed_filename.hexdigest()[0:2]

	filename_quoted = urllib.quote_plus(filename)	
	
	# peculiars for Fedora
	####################################################
	filename_quoted = filename_quoted.replace('_','%5F')
	####################################################

	# symlink directory
	path_prefix = "/var/www/wsuls/symLinks/"
	
	# guess file extension
	try:		
		extension_guess = mimetypes.guess_extension( fedora_handle.get_object(PID).getDatastreamObject(DS).mimetype )
		if extension_guess == None:
			extension_guess == ".sym"
	except:
		extension_guess = ".sym"

	# construct full symlink path
	file_path = path_prefix+hashed_filename.hexdigest()+extension_guess
	
	returnDict['symlink'] = file_path;	

	# exists
	if os.path.exists(file_path):
		return returnDict
	# create
	else:
		source_prefix = "/usr/local/fedora/data/datastreamStore/"
		source_path = source_prefix+dataFolder+"/"+filename_quoted

		if os.path.exists(source_path):
			os.symlink(source_path, file_path)
			return returnDict
		else:
			return "Target not found.  Aborting."


