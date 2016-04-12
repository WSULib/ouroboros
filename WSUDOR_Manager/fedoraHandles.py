# fedora handles
from eulfedora.server import Repository
from localConfig import *

fedora_handle = 'temp'

# local repository handle
fedora_handle_apia = Repository(
	FEDORA_ROOT,
	FEDORA_USER_APIA,
	FEDORA_PASSWORD_APIA,
	'wayne')

# yield remote repository handle from localConfig
def remoteRepo(name):
	return  Repository(
	REMOTE_REPOSITORIES[name]['FEDORA_ROOT'],
	REMOTE_REPOSITORIES[name]['FEDORA_USERNAME'],
	REMOTE_REPOSITORIES[name]['FEDORA_PASSWORD'],
	'wayne')
