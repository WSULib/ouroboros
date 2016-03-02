# fedora handles
from eulfedora.server import Repository
from localConfig import *

# local repository handle
fedora_handle = Repository(
	REMOTE_REPOSITORIES[REPOSITORY_NAME]['FEDORA_ROOT'],
	REMOTE_REPOSITORIES[REPOSITORY_NAME]['FEDORA_USERNAME'],
	REMOTE_REPOSITORIES[REPOSITORY_NAME]['FEDORA_PASSWORD'],
	'wayne')

# yield remote repository handle from localConfig
def remoteRepo(name):
	return  Repository(
	REMOTE_REPOSITORIES[name]['FEDORA_ROOT'],
	REMOTE_REPOSITORIES[name]['FEDORA_USERNAME'],
	REMOTE_REPOSITORIES[name]['FEDORA_PASSWORD'],
	'wayne')
