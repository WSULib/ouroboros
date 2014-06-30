'''
Contains all tasks that can be performed by fedoraManager2
They can be self contained here, or simple function definitions that import more complicated behavior.

views.py wil be grabbing the function name directly from this, so they must bubble up to this level.

In a sense, this file is a glorified importer.

A typical task module that has its own folder, might be structured like so:

/////////////////////////
DCfromMODS
	__init__.py
	main.py (contains function that matches URL, e.g. /fireTask/DCfromMODS")
	other_helpful_thing.py
/////////////////////////
'''

# sys
import time
import os

# handles
from fedoraManager2.solrHandles import solr_handle
from fedoraManager2.fedoraHandles import fedora_handle


# IMPORTED TASKS
############################################################
from DCfromMODS.main import *
from editRELS.main import *



# LOCALLY DEFINED
############################################################
# test task, small delay
def sampleTask(job_package):	
	username = job_package['username']
	# delay for testing		
	time.sleep(2)	
	return 40 + 2

# test task, no delay
def sampleFastTask(job_package):
	username = job_package['username']	
	return 40 + 2

# fedora function, get label
def labelPrint(job_package):		
	print "Running fedoraTesting"
	PID= job_package['PID']		
	obj_ohandle = fedora_handle.get_object(PID)
	print obj_ohandle.label	





