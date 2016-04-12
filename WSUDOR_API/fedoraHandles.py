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


