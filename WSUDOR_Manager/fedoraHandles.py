# fedora handles
from eulfedora.server import Repository
from localConfig import *

# local repository handle
fedora_handle = Repository(
	FEDORA_ROOT,
	WSUDOR_API_USER,
	WSUDOR_API_PASSWORD,
	'wayne'
)

# yield remote repository handle from localConfig
def remoteRepo(name):
	return  Repository(
	REMOTE_REPOSITORIES[name]['FEDORA_ROOT'],
	REMOTE_REPOSITORIES[name]['FEDORA_USERNAME'],
	REMOTE_REPOSITORIES[name]['FEDORA_PASSWORD'],
	'wayne')
