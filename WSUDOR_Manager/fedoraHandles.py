# fedora handles
from eulfedora.server import Repository
from localConfig import *
from WSUDOR_Manager import fedora_handle


# if celery worker, fire fedora_handle with auth credentials
if fedora_handle == False:

	print "creating user authenticated fedora_handle"
	
	# retrieve user creds from...

	# uesr authenticated repository handle
	fedora_handle = Repository(FEDORA_ROOT, 'fedoraAdmin', 'fedorapassword', 'wayne')



# yield remote repository handle from localConfig
def remoteRepo(name):
	return  Repository(
	REMOTE_REPOSITORIES[name]['FEDORA_ROOT'],
	REMOTE_REPOSITORIES[name]['FEDORA_USERNAME'],
	REMOTE_REPOSITORIES[name]['FEDORA_PASSWORD'],
	'wayne')
