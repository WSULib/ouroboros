import time

def fileWrite(job_package):
	time.sleep(.25)
	filename = "test_output.out"
	fhand = open(filename,'a')
	fhand.write("Step: {step}\n".format(step=job_package['step']))
	fhand.close()