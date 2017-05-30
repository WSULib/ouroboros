from WSUDOR_Manager import *
from WSUDOR_Manager import jobs
logging.debug("importing WSUDOR_Manager")
import WSUDOR_Indexer
from WSUDOR_Indexer.models import IndexRouter

# python
import os
import rdflib
import time

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

logging.debug("importing fedora handles")
fedora_handle = fedoraHandles.fedora_handle
from WSUDOR_Manager import fedoraHandles

logging.debug("importing solr handles")
solr_handle = solrHandles.solr_handle
solr_bookreader_handle = solrHandles.solr_bookreader_handle

logging.debug("creating WSUDOR shortcuts")
w = WSUDOR_ContentTypes.WSUDOR_Object

from WSUDOR_API.v2.inc.oai import OAIProvider, OAIRecord

logging.debug("importing eulfedora")

import eulfedora

from WSUDOR_Manager.lmdbHandles import lmdb_env

logging.debug("creating MySQL shortcut - `m()` with root password")
def my():
	return os.system('mysql -u root -p WSUDOR_Manager')

logging.debug("creating bash shortcut - 'bash'")
def bash():
	return os.system('bash')

# DEBUG
def tableWipe():
	try:
		db.session.execute('DROP TABLE ingest_workspace_object;')
		logging.debug("ingest_workspace_object dropped.")
	except:
		logging.debug("ingest_workspace_object not found...")
	try:
		db.session.execute('DROP TABLE ingest_workspace_job;')
		logging.debug("ingest_workspace_job dropped.")
	except:
		logging.debug("ingest_workspace_job not found...")
	try:
		db.session.execute('DROP TABLE user;')
		logging.debug("user dropped.")
	except:
		logging.debug("user not found...")
	try:
		db.session.execute('DROP TABLE ingest_MODS;')
		logging.debug("ingest_MODS dropped.")
	except:
		logging.debug("ingest_MODS not found...")
	try:
		db.session.execute('DROP TABLE job_rollback;')
		logging.debug("job_rollback dropped.")
	except:
		logging.debug("job_rollback not found...")
	try:
		db.session.execute('DROP TABLE user_jobs;')
		logging.debug("user_jobs dropped.")
	except:
		logging.debug("user_jobs not found...")
	try:
		db.session.execute('DROP TABLE user_pids;')
		logging.debug("user_pids dropped.")
	except:
		logging.debug("user_pids not found...")
	try:
		db.session.execute('DROP TABLE xsl_transformations;')
		logging.debug("xsl_transformations dropped.")
	except:
		logging.debug("xsl_transformations not found...")
	try:
		db.session.execute('DROP TABLE indexer_queue;')
		logging.debug("indexer_queue dropped.")
	except:
		logging.debug("indexer_queue not found...")
	logging.debug("commiting...")
	db.session.commit()

	logging.debug("recreating...")
	db.create_all()

	logging.debug("recreating default admin users")
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
	os.system("tail -f /var/log/celery-%s.out.log" % user)


# function to grab single object from remote repository
def getRemoteObject(repo, base_pid, skip_constituents=False):

	logging.info("ingesting: %s" % base_pid)
	sync_list = [base_pid]
	
	# remote repo
	dest_repo_handle = fedoraHandles.remoteRepo(repo)
	
	# check if remote object has constituent parts
	if not skip_constituents:
		constituents = dest_repo_handle.risearch.spo_search(None,"fedora-rels-ext:isConstituentOf","info:fedora/%s" % base_pid)
		logging.debug(len(constituents))
		if len(constituents) > 0:
			for constituent in constituents:
				# add to sync list
				logging.debug("adding %s to sync list" % constituent[0])
				sync_list.append(constituent[0])
			
	# sync objects 
	for i,pid in enumerate(sync_list):

		# add sync_list to indexer queue with 'hold' action to prevent indexing
		if pid.startswith("info:fedora/"):
			pid = pid.split("/")[1]
		IndexRouter.queue_object(pid, priority=1, username='console', action='hold')

		logging.debug("retrieving %s, %d/%d..." % (pid,i,len(sync_list)))
		logging.debug(eulfedora.syncutil.sync_object(dest_repo_handle.get_object(pid), fedora_handle, show_progress=False, export_context='archive'))

	# ingest complete, remove all from indexer queue hold
	for i,pid in enumerate(sync_list):
		if pid.startswith("info:fedora/"):
			pid = pid.split("/")[1]
		# release from indexer hold
		if i > 0:
			logging.debug("releasing from indexer queue hold: %s, %d/%d..." % (pid,i,len(sync_list)))
			IndexRouter.alter_queue_action(pid, 'forget')

	# finally, let primary object index
	IndexRouter.alter_queue_action(base_pid, 'forget')

	# refresh
	obj = w(base_pid)
	obj.refresh()

	return True
	
	
# function to clone object datastream by datastream
def cloneRemoteObject(repo, PID):
	pass
	

def getIngestWorkspaceRows(job_num):
	iwjob = models.ingest_workspace_job.query.filter_by(id=job_num).first()
	iwrows = models.ingest_workspace_object.query.filter_by(job=iwjob)
	logging.debug("returning tuple of (job_handle, job_rows)")
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
		logging.debug("##############################################################################")
		logging.debug("working on %s / %s" % (index, len(seed_pids)))
		logging.debug("##############################################################################")
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
						logging.debug("could not index %s" % pid)
				else:
					raise Exception
			except:
				logging.debug("-------------------------------------------------------------------------------")
				logging.debug("FAILURE: %s" % pid)
				logging.debug("-------------------------------------------------------------------------------")
		except:
			logging.debug("Could not get remote object: %s" % pid)

	logging.debug('finis.')

	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	


