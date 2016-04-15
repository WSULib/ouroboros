# fedora handles
from eulfedora.server import Repository
from localConfig import *

# local repository handle
'''
Username and Password are False by default, not needed for API-A
'''
fedora_handle = Repository(
	FEDORA_ROOT,
	False,
	False,
	'wayne'
)


