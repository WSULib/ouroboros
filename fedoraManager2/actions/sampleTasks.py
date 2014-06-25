import time

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