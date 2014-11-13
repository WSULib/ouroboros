# fedora handles
from eulfedora.server import Repository
from localConfig import *

fedora_handle = Repository(FEDORA_ROOT,FEDORA_USER,FEDORA_PASSWORD,FEDORA_PIDSPACE)