# fedora handles
from eulfedora.server import Repository
from localConfig import *
from WSUDOR_Manager import fedora_handle, app


# if celery worker, fire fedora_handle with auth credentials
if fedora_handle == False:

	print "creating user authenticated fedora_handle"
	
	# retrieve user creds from DB
	from WSUDOR_Manager import models
	user = models.User.query.filter_by(username=app.config['USERNAME']).first()
	print "using auth %s / %s" % (user.username,user.password)

	# uesr authenticated repository handle
	fedora_handle = Repository(FEDORA_ROOT, user.username, user.password, 'wayne')



# yield remote repository handle from localConfig
def remoteRepo(name):
	return  Repository(
	REMOTE_REPOSITORIES[name]['FEDORA_ROOT'],
	REMOTE_REPOSITORIES[name]['FEDORA_USERNAME'],
	REMOTE_REPOSITORIES[name]['FEDORA_PASSWORD'],
	'wayne')
