print "importing WSUDOR_Manager"
from WSUDOR_Manager import *
from WSUDOR_Manager import jobs
import WSUDOR_Indexer

# python
import os
import rdflib
import time

# set logging level
logging.basicConfig(level=logging.INFO)

print '''
                ::+:/`
         :----:+ssoo+:.`
      `-:+sssossysoooooo+/-`
    `:oysyo++ooooo+////+ooss+-`
   :ssyy/-`   `..     ..:/+osso:
 `/ssyo:                 `-+:oss+`
 +sso+:                    `//sss+
.sssoo`                     `o+sss:
/syso+                    `-`+ooss+
ssyoo+                    ../oossss
osso+o.                  `+//ooysoo
:ysyo+o.                  `/++osos:
`+ssssoo:`   ``.-` .-    `-ooosss+`
 `ossso///-.--:.``::. `.:+ooossso`
  `+sossyo++o++::///:/+ooossoss+`
    -ossssss+oo+sossoosossssso-
      ./osssssysyysssssssso/.
         `-:++sosyssyyo+:.

  <-- Ouroboros says hissss -->'''

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
	try:
		db.session.execute('DROP TABLE ingest_MODS;')
		print "ingest_MODS dropped."
	except:
		print "ingest_MODS not found..."
	try:
		db.session.execute('DROP TABLE job_rollback;')
		print "job_rollback dropped."
	except:
		print "job_rollback not found..."
	try:
		db.session.execute('DROP TABLE user_jobs;')
		print "user_jobs dropped."
	except:
		print "user_jobs not found..."
	try:
		db.session.execute('DROP TABLE user_pids;')
		print "user_pids dropped."
	except:
		print "user_pids not found..."
	try:
		db.session.execute('DROP TABLE xsl_transformations;')
		print "xsl_transformations dropped."
	except:
		print "xsl_transformations not found..."
	try:
		db.session.execute('DROP TABLE indexer_queue;')
		print "indexer_queue dropped."
	except:
		print "indexer_queue not found..."
	print "commiting..."
	db.session.commit()

	print "recreating..."
	db.create_all()

	print "recreating default admin users"
	for user in localConfig.DEFAULT_ADMIN_USERS:
		user = models.User(
			user['username'],
			user['role'],
			user['displayName']
		)
		db.session.add(user)
		db.session.commit()

# logs
def tailUserCelery(user):
	os.system("tail -f /var/log/celery-%s.err.log" % user)


# function to grab single object from remote repository
def getRemoteObject(repo, PID, skip_constituents=False):
	
	sync_list = [PID]
	
	# remote repo
	dest_repo_handle = fedoraHandles.remoteRepo(repo)
	
	# check if remote object has constituent parts
	if not skip_constituents:
		constituents = dest_repo_handle.risearch.spo_search(None,"fedora-rels-ext:isConstituentOf","info:fedora/%s" % PID)
		print len(constituents)
		if len(constituents) > 0:
			for constituent in constituents:
				# add to sync list
				print "adding %s to sync list" % constituent[0]
				sync_list.append(constituent[0])
			
	# sync objects 
	for i,pid in enumerate(sync_list):
		print "retrieving %s, %d/%d..." % (pid,i,len(sync_list))
		print eulfedora.syncutil.sync_object(dest_repo_handle.get_object(pid), fedora_handle, show_progress=False, export_context='archive')

	return True
	
	
# function to clone object datastream by datastream
def cloneRemoteObject(repo, PID):
	pass
	

def getIngestWorkspaceRows(job_num):
	iwjob = models.ingest_workspace_job.query.filter_by(id=job_num).first()
	iwrows = models.ingest_workspace_object.query.filter_by(job=iwjob)
	print "returning tuple of (job_handle, job_rows)"
	return (iwjob,iwrows)
	
def getSeedObjects(target_repo):
	seed_pids = [
		# vmc (single image)
		'wayne:collectionvmc',
		'wayne:vmc15687',
		'wayne:vmc14515',
		# van riper (complex)
		'wayne:collectionVanRiperLetters',
		'wayne:MSS-001-006-005',
		# ramsey (ebooks)
		'wayne:collectionRamsey',
		'wayne:Almanackfo1887b4801574x',
		# lincoln (learning objects)
		'wayne:collectionLincolnLetters',
		'wayne:LearningObject_1b20d1e4-b67b-4e6b-93e5-502b5614178d',
		'wayne:LearningObject_File_d1ddc9e9-032a-4479-a5b1-5c0728700ed9',
		'wayne:LincolnLettersFHC205771',
		# Swanger (hierarchical)
		'wayne:collectionSwanger',
		'wayne:Swanger1777Series3',
		'wayne:Swanger1777_8_10',
		'wayne:Swanger1777_8_10_03',
		'wayne:Swanger1777_8_11',
		'wayne:Swanger1777_8_11_01',
		'wayne:Swanger1777Series2',
		'wayne:Swanger1777_1_40',
		'wayne:Swanger1777_1_40_01'
	]

	# get objects and index
	for index, pid in enumerate(seed_pids):
		# try:
		print "##############################################################################"
		print "working on %s / %s" % (index, len(seed_pids))
		print "##############################################################################"
		try:
			remote_get = getRemoteObject(target_repo,pid)

			try:
				if remote_get:
					while True:
						obj_test = fedora_handle.get_object(pid)
						if obj_test.exists == True:
							break
						else:
							time.sleep(.5)
					obj = w(pid)
					try:
						obj.refresh()
					except:
						print "could not index %s" % pid
				else:
					raise Exception
			except:
				print "-------------------------------------------------------------------------------"
				print "FAILURE: %s" % pid
				print "-------------------------------------------------------------------------------"
		except:
			print "Could not get remote object: %s" % pid

	print 'finis.'

	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	


