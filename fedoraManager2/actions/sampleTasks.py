import time

from eulfedora.server import Repository
from sensitive import *



def sampleTask(job_package):
	# task
	username = job_package['username']

	# delay for testing		
	time.sleep(2)	
	
	# return results
	return 40 + 2


def sampleFastTask(job_package):
	username = job_package['username']

	# return results
	return 40 + 2

def checksumTest(job_package):
		
	print "Running checksumTest"
	PID= job_package['PID']
	# init FC connection
	repo = Repository(FEDORA_ROOT,FEDORA_USER,FEDORA_PASSWORD,FEDORA_PIDSPACE)
	obj_ohandle = repo.get_object(PID)
	print obj_ohandle.label	