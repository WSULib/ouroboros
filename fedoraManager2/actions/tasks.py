'''
Contains all tasks that can be performed by fedoraManager2
They can be self contained here, or simple function definitions that import more complicated behavior
'''

import time
import os


from fedoraManager2.solrHandles import solr_handle
from fedoraManager2.fedoraHandles import fedora_handle

import DCfromMODS_mod.DCfromMODS_main


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
def fedoraTesting(job_package):		
	print "Running fedoraTesting"
	PID= job_package['PID']		
	obj_ohandle = fedora_handle.get_object(PID)
	print obj_ohandle.label	



# os testing
def DCfromMODS(job_package):		
	print "Running DCfromMODS"
	DCfromMODS_mod.DCfromMODS_main.DCfromMODS(job_package['PID'])		
	


