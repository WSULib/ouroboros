# fedora handles
from eulfedora.server import Repository
from localConfig import *
from WSUDOR_Manager import fedora_handle

# # local repository handle
# fedora_handle = Repository(
# 	FEDORA_ROOT,
# 	False,
# 	False,
# 	'wayne'
# )



# yield remote repository handle from localConfig
def remoteRepo(name):
	return  Repository(
	REMOTE_REPOSITORIES[name]['FEDORA_ROOT'],
	REMOTE_REPOSITORIES[name]['FEDORA_USERNAME'],
	REMOTE_REPOSITORIES[name]['FEDORA_PASSWORD'],
	'wayne')
