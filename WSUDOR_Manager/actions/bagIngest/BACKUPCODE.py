# job kickoff
@bagIngest.route('/bagIngest/ingest', methods=['POST', 'GET'])
def bagIngest_router():	
	# get new job num
	job_num = jobs.jobStart()

	# get username
	username = session['username']			

	# prepare job_package for boutique celery wrapper
	job_package = {
		'job_num':job_num,
		'task_name':"bagIngest_worker",
		'form_data':request.form
	}	

	# job celery_task_id
	celery_task_id = celeryTaskFactoryBagIngest.delay(job_num,job_package)		 

	# send job to user_jobs SQL table
	db.session.add(models.user_jobs(job_num, username, celery_task_id, "init", "singleBagItIngest"))	
	db.session.commit()		

	print "Started job #",job_num,"Celery task #",celery_task_id
	return redirect("/userJobs")




@celery.task(name="celeryTaskFactoryBagIngest")
def celeryTaskFactoryBagIngest(job_num,job_package):
	
	# reconstitute
	job_num = job_package['job_num']	

	# update job info
	'''
	sets estimate to one, not accurate
	'''
	redisHandles.r_job_handle.set("job_{job_num}_est_count".format(job_num=job_num),1)

	# ingest in Fedora
	step = 1

	job_package['PID'] = "N/A"
	job_package['step'] = step		

	# fire ingester
	result = actions.actions.taskWrapper.delay(job_package)	

	task_id = result.id		
	print task_id
		
	# update incrementer for total assigned
	jobs.jobUpdateAssignedCount(job_num)

	# bump step
	step += 1


def bagIngest_worker(job_package):	

	# get form data
	form_data = job_package['form_data']
	if "ingest_type" in form_data:
		ingest_type = form_data['ingest_type']
	else:
		return "No ingest type selected, aborting."

	if ingest_type == "single":
		singleBag_ingest_worker(job_package)

	if ingest_type == "multiple":
		multipleBag_ingest_worker(job_package)


def singleBag_ingest_worker(job_package):
	'''
	This function expects a single BagIt object, either directory or archive, for ingest.
	'''

	# extract payload_location
	payload_location = job_package['form_data']['payload_location']
	ingest_type = job_package['form_data']['ingest_type']

	# create working directory in workspace
	bag_dir = payloadExtractor(payload_location,ingest_type)

	return ingestBag(bag_dir)



def multipleBag_ingest_worker(job_package):

	'''
	This function expects multiple BagIt objects, either directory or archive, for ingest.	
	'''

	# extract payload_location
	payload_location = job_package['form_data']['payload_location']
	ingest_type = job_package['form_data']['ingest_type']

	# create working directory in workspace
	bag_dir = payloadExtractor(payload_location,ingest_type)
	if bag_dir == False:
		print "Aborting"
		return False
	print "Bag dir at this point:",bag_dir

	# all items inside bag_dir	
	bag_dirs_tuple = os.walk(bag_dir).next()

	# dirs
	if len(bag_dirs_tuple[1]) > 0:
		print "Directories detected, continuing"

	# archives
	if len(bag_dirs_tuple[2]) > 0:
		print "Archive files detected. Extracting and continuing."
		for archive in bag_dirs_tuple[2]:
			archive_filename = bag_dirs_tuple[0] + "/" + archive
			print archive_filename

			# extract to temp dir
			tar_handle = tarfile.open(archive_filename)
			tar_handle.extractall(path=bag_dirs_tuple[0])
			os.system("rm {archive_filename}".format(archive_filename=archive_filename))

		# finally, rewalk
		bag_dirs_tuple = os.walk(bag_dir).next()

	# dirs
	bag_dirs = [ bag_dirs_tuple[0] + "/" + bag_name for bag_name in bag_dirs_tuple[1] ]
	print bag_dirs

	# iterate through BagIt dirs
	count = 1
	for bag in bag_dirs:
		print "Ingesting {count} / {total}".format(count=count,total=len(bag_dirs))
		ingestBag(bag)
		count += 1

	print "Batch ingest complete."
	return True


 
def payloadExtractor(payload_location,ingest_type):	
	
	'''
	function to detect archive or dir, extract where necessary, and return path (bag_dir) of extracted directory in workspace
	'''

	# payload as archive
	if os.path.isfile(payload_location):
		print "payload_location is a file, extracting archive of BagIt directory(s)"
		archive_filename = os.path.basename(payload_location)

		# move file
		os.system("cp {payload_location} /tmp/Ouroboros/ingest_workspace/".format(payload_location=payload_location))

		# extract to temp dir
		temp_dir = str(uuid.uuid4())
		tar_handle = tarfile.open("/tmp/Ouroboros/ingest_workspace/{archive_filename}".format(archive_filename=archive_filename))
		tar_handle.extractall(path="/tmp/Ouroboros/ingest_workspace/{temp_dir}".format(temp_dir=temp_dir))

		# remove archive after copy
		os.system("rm /tmp/Ouroboros/ingest_workspace/{archive_filename}".format(archive_filename=archive_filename))

		# extracted bag_dir for single, return directory of single BagIt directory
		if ingest_type == "single":
			bag_dir = os.walk("/tmp/Ouroboros/ingest_workspace/{temp_dir}".format(temp_dir=temp_dir)).next()[1][0]
			bag_dir = "/tmp/Ouroboros/ingest_workspace/{temp_dir}/".format(temp_dir=temp_dir) + bag_dir

		# extracted bag_dir for multiple, return temp directory full of BagIt archives
		if ingest_type == "multiple":
			bag_dir = "/tmp/Ouroboros/ingest_workspace/{temp_dir}".format(temp_dir=temp_dir)

		return bag_dir


	# payload as directory
	elif os.path.isdir(payload_location):
		print "payload_location is a dir, no extraction required"
		bag_dir = payload_location
		return bag_dir


	# payload not file or dir
	else:
		print "payload_location does not appear to be a valid directory or file, or cannot be found at all.  Aborting."
		return False


		
def ingestBag(bag_dir):

	# load bag_handle and ingest	
	print "Working on:",bag_dir
	bag_handle = WSUDOR_ContentTypes.WSUDOR_Object(object_type="bag", payload=bag_dir)
	if bag_dir == 'Could not load WSUDOR or Bag object.':
		print "Aborting, bag_handle initiziation was unsuccessful."
		return False
	
	# validate bag for WSUDOR ingest	
	valid_results = bag_handle.validIngestBag()
	if valid_results['verdict'] != True:
		print "Bag is not valid for the following reasons, aborting.", valid_results
		return False

	# ingest bag
	ingest_bag = bag_handle.ingestBag()

	# Remove bag_dir (temp location for archive, original payload_location for dir)
	# os.system("rm -r {bag_dir}".format(bag_dir=bag_dir))

	return json.dumps({"Ingest Results for {bag_label}, PID: {bag_pid}".format(bag_label=bag_handle.label.encode('utf-8'),bag_pid=bag_handle.pid):ingest_bag})



# -------------------------------------------------------------------------------------------------------------------------------------------------------------------------#
# Ingest and Push
# singleBag worker
@bagIngestAndPush.route('/bagIngestAndPush/ingest', methods=['POST', 'GET'])
def bagIngestAndPush_router():	

	# get new job num
	job_num = jobs.jobStart()

	# get username
	username = session['username']			

	# prepare job_package for boutique celery wrapper
	job_package = {
		'job_num':job_num,
		'task_name':"bagIngestAndPush_worker",
		'form_data':request.form
	}	

	# job celery_task_id
	celery_task_id = celeryTaskFactorybagIngestAndPush.delay(job_num,job_package)		 

	# send job to user_jobs SQL table
	db.session.add(models.user_jobs(job_num, username, celery_task_id, "init", "singleBagItIngest"))	
	db.session.commit()		

	print "Started job #",job_num,"Celery task #",celery_task_id
	return redirect("/userJobs")



@celery.task(name="celeryTaskFactorybagIngestAndPush")
def celeryTaskFactorybagIngestAndPush(job_num,job_package):
	
	# reconstitute
	job_num = job_package['job_num']	

	# update job info
	redisHandles.r_job_handle.set("job_{job_num}_est_count".format(job_num=job_num),1)

	# ingest in Fedora
	step = 1

	job_package['PID'] = "N/A"
	job_package['step'] = step		

	# fire ingester
	result = actions.actions.taskWrapper.delay(job_package)	

	task_id = result.id		
	print task_id
		
	# update incrementer for total assigned
	jobs.jobUpdateAssignedCount(job_num)

	# bump step
	step += 1


def bagIngestAndPush_worker(job_package):	

	# get form data
	form_data = job_package['form_data']
	if "ingest_type" in form_data:
		ingest_type = form_data['ingest_type']
	else:
		return "No ingest type selected, aborting."

	if ingest_type == "single":
		singleBag_ingest_worker(job_package)

	if ingest_type == "multiple":
		multipleBag_ingest_worker(job_package)


def singleBag_ingest_worker(job_package):
	'''
	This function expects a single BagIt object, either directory or archive, for ingest.
	'''

	# extract payload_location
	payload_location = job_package['form_data']['payload_location']
	ingest_type = job_package['form_data']['ingest_type']

	# set destination repo
	dest_repo = job_package['form_data']['dest_repo']

	# get export context
	export_context = job_package['form_data']['export_context']

	# overwrite
	if 'overwrite' in job_package['form_data']:
		overwrite = True
	else:
		overwrite = False

	# refresh remote
	if 'refresh_remote' in job_package['form_data']:
		refresh_remote = True
	else:
		refresh_remote = False

	# create working directory in workspace
	bag_dir = payloadExtractor(payload_location,ingest_type)

	return ingestBagAndPush(bag_dir, dest_repo, refresh_remote=refresh_remote, export_context=export_context, overwrite=overwrite)



def multipleBag_ingest_worker(job_package):

	'''
	This function expects multiple BagIt objects, either directory or archive, for ingest.	
	'''

	# extract payload_location
	payload_location = job_package['form_data']['payload_location']
	ingest_type = job_package['form_data']['ingest_type']

	# set destination repo
	dest_repo = job_package['form_data']['dest_repo']

	# get export context
	export_context = job_package['form_data']['export_context']

	# overwrite
	if 'overwrite' in job_package['form_data']:
		overwrite = True
	else:
		overwrite = False

	# refresh remote
	if 'refresh_remote' in job_package['form_data']:
		refresh_remote = True
	else:
		refresh_remote = False

	# create working directory in workspace
	bag_dir = payloadExtractor(payload_location,ingest_type)
	if bag_dir == False:
		print "Aborting"
		return False
	print "Bag dir at this point:",bag_dir

	# all items inside bag_dir	
	bag_dirs_tuple = os.walk(bag_dir).next()

	# dirs
	if len(bag_dirs_tuple[1]) > 0:
		print "Directories detected, continuing"

	# archives
	if len(bag_dirs_tuple[2]) > 0:
		print "Archive files detected. Extracting and continuing."
		for archive in bag_dirs_tuple[2]:
			archive_filename = bag_dirs_tuple[0] + "/" + archive
			print archive_filename

			# extract to temp dir
			tar_handle = tarfile.open(archive_filename)
			tar_handle.extractall(path=bag_dirs_tuple[0])
			os.system("rm {archive_filename}".format(archive_filename=archive_filename))

		# finally, rewalk
		bag_dirs_tuple = os.walk(bag_dir).next()

	# dirs
	bag_dirs = [ bag_dirs_tuple[0] + "/" + bag_name for bag_name in bag_dirs_tuple[1] ]
	print bag_dirs

	# iterate through BagIt dirs
	count = 1
	for bag in bag_dirs:
		try:
			print "Working on",bag
			print "Ingesting {count} / {total}".format(count=count,total=len(bag_dirs))
			print ingestBagAndPush(bag, dest_repo, refresh_remote=refresh_remote, export_context=export_context, overwrite=overwrite)
			count += 1
		except:
			print "########## INGEST FAILURE ON",bag,"##############"

	print "Batch ingest complete."
	return True


 
def payloadExtractor(payload_location,ingest_type):	
	
	'''
	function to detect archive or dir, extract where necessary, and return path (bag_dir) of extracted directory in workspace
	'''

	# payload as archive
	if os.path.isfile(payload_location):
		print "payload_location is a file, extracting archive of BagIt directory(s)"
		archive_filename = os.path.basename(payload_location)

		# move file
		os.system("cp {payload_location} /tmp/Ouroboros/ingest_workspace/".format(payload_location=payload_location))

		# extract to temp dir
		temp_dir = str(uuid.uuid4())
		tar_handle = tarfile.open("/tmp/Ouroboros/ingest_workspace/{archive_filename}".format(archive_filename=archive_filename))
		tar_handle.extractall(path="/tmp/Ouroboros/ingest_workspace/{temp_dir}".format(temp_dir=temp_dir))

		# remove archive after copy
		os.system("rm /tmp/Ouroboros/ingest_workspace/{archive_filename}".format(archive_filename=archive_filename))

		# extracted bag_dir for single, return directory of single BagIt directory
		if ingest_type == "single":
			bag_dir = os.walk("/tmp/Ouroboros/ingest_workspace/{temp_dir}".format(temp_dir=temp_dir)).next()[1][0]
			bag_dir = "/tmp/Ouroboros/ingest_workspace/{temp_dir}/".format(temp_dir=temp_dir) + bag_dir

		# extracted bag_dir for multiple, return temp directory full of BagIt archives
		if ingest_type == "multiple":
			bag_dir = "/tmp/Ouroboros/ingest_workspace/{temp_dir}".format(temp_dir=temp_dir)

		return bag_dir


	# payload as directory
	elif os.path.isdir(payload_location):
		print "payload_location is a dir, no extraction required"
		bag_dir = payload_location
		return bag_dir


	# payload not file or dir
	else:
		print "payload_location does not appear to be a valid directory or file, or cannot be found at all.  Aborting."
		return False


		
def ingestBagAndPush(bag_dir, dest_repo, refresh_remote=True, overwrite=False, export_context='migrate'):

	# DEBUG
	print dir(localConfig)

	# load bag_handle and ingest	
	print "Working on:",bag_dir
	bag_handle = WSUDOR_ContentTypes.WSUDOR_Object(object_type="bag", payload=bag_dir)
	if bag_dir == 'Could not load WSUDOR or Bag object.':
		print "Aborting, bag_handle initiziation was unsuccessful."
		return False
	
	# validate bag for WSUDOR ingest	
	valid_results = bag_handle.validIngestBag()
	if valid_results['verdict'] != True:
		print "Bag is not valid for the following reasons, aborting.", valid_results
		return False

	# ingest bag & skip indexing
	ingest_bag = bag_handle.ingestBag(indexObject=False)

	# push to remote repo
	print "sending object..."

	# Use object method
	obj_handle = WSUDOR_ContentTypes.WSUDOR_Object(bag_handle.pid)
	obj_handle.sendObject(dest_repo, refresh_remote=refresh_remote, overwrite=overwrite, export_context=export_context)	

	# delete local object
	print "finally, removing object"
	fedora_handle.purge_object(bag_handle.pid)

	# remove from Solr	
	solr_handle.delete_by_key(bag_handle.pid)

	return json.dumps({"Ingest Results for {bag_label}, PID: {bag_pid}".format(bag_label=bag_handle.label.encode('utf-8'),bag_pid=bag_handle.pid):True})