print "importing WSUDOR_Manager"
from WSUDOR_Manager import *

# python
import os

print "importing fedora handles"
fedora_handle = fedoraHandles.fedora_handle
from WSUDOR_Manager import fedoraHandles

print "importing solr handles"
solr_handle = solrHandles.solr_handle
solr_bookreader_handle = solrHandles.solr_bookreader_handle

print "creating WSUDOR shortcuts"
w = WSUDOR_ContentTypes.WSUDOR_Object

print "importing eulfedora"
import eulfedora

print "creating MySQL shortcut - `m()` with root password"
def my():
	return os.system('mysql -u root -p WSUDOR_Manager')

print "creating bash shortcut - 'bash'"
def bash():
	return os.system('bash')

# DEBUG
def tableWipe():
	try:
		db.session.execute('DROP TABLE ingest_workspace_object;')
		print "ingest_workspace_object dropped."
	except:
		print "ingest_workspace_object not found..."
	try:
		db.session.execute('DROP TABLE ingest_workspace_job;')
		print "ingest_workspace_job dropped."
	except:
		print "ingest_workspace_job not found..."
	try:
		db.session.execute('DROP TABLE user;')
		print "user dropped."
	except:
		print "user not found..."
	print "commiting..."
	db.session.commit()

	print "recreating..."
	db.create_all()

# logs
def tailUserCelery(user):
	os.system("tail -f /var/log/celery-%s.err.log" % user)


# Ouroverse

# function to grab single object from remote repository
def getRemoteObject(repo, PID, index=True):
	return eulfedora.syncutil.sync_object(fedoraHandles.remoteRepo(repo).get_object(PID), fedora_handle, show_progress=False, export_context='archive')
	if index:
		obj = w(PID)
		print "waiting momentarily for object to finish ingesting..."
		time.sleep(3)
		obj.objectRefresh()


