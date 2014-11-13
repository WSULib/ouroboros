# KEEP AS REFERENCE
# # export WSUDOR objectBag
# def exportBagGeneric(self):
# 	'''
# 	This function expects an eulfedora object, then exports entire object as WSUDOR objectBag.
# 	We will want to return a Bag object, complete with the manifest information.
# 	We will probably want to use bagit.make_bag, perhaps with the result of this file?
# 	Yes.  Export to directory, THEN make bag of that.  If all goes as planned, the
# 	checksums should match the original checksums.  

# 	Validating that would be possible.		
# 	'''

# 	# create temp dir
# 	temp_dir = "/tmp/Ouroboros/bagging_area/{pid_suffix}".format(pid_suffix=self.pid_suffix)		
# 	os.system("mkdir {temp_dir}".format(temp_dir=temp_dir))

# 	# export MODS
# 	fhand = open("{temp_dir}/MODS.xml".format(temp_dir=temp_dir), "w")
# 	MODS_handle = self.ohandle.getDatastreamObject("MODS")
# 	fhand.write(MODS_handle.content.serialize())
# 	fhand.close()

# 	# export RELS-EXT
# 	fhand = open("{temp_dir}/RELS-EXT.xml".format(temp_dir=temp_dir), "w")
# 	RELS_handle = self.ohandle.getDatastreamObject("RELS-EXT")
# 	fhand.write(RELS_handle.content.serialize())
# 	fhand.close()

# 	# export POLICY
# 	fhand = open("{temp_dir}/POLICY.xml".format(temp_dir=temp_dir), "w")
# 	POLICY_handle = self.ohandle.getDatastreamObject("POLICY")
# 	fhand.write(RELS_handle.content.serialize())
# 	fhand.close()

# 	# for datastream in remaining datastreams, export to /datastreams directory		
# 	os.system("mkdir {temp_dir}/datastreams".format(temp_dir=temp_dir))

# 	for DS in self.ohandle.ds_list:
		
# 		if DS in ['MODS','RELS-EXT','POLICY']:
# 			continue

# 		DS_handle = self.ohandle.getDatastreamObject(DS)

# 		print "Mime type: {mimetype}. Guessed file extension: {guess}".format(mimetype=DS_handle.mimetype,guess=mimetypes.guess_extension(DS_handle.mimetype))

# 		fhand = open("{temp_dir}/datastreams/{DS_ID}{extension_guess}".format(temp_dir=temp_dir,DS_ID=DS_handle.id, extension_guess=mimetypes.guess_extension(DS_handle.mimetype)), "wb")
# 		if DS_handle.control_group == "M":			
# 			fhand.write(DS_handle.content)
# 		if DS_handle.control_group == "X":			
# 			fhand.write(DS_handle.content.serialize())
# 		fhand.close()


# 	# finally, create bag
# 	bag = bagit.make_bag(temp_dir, {'Contact-Name': 'Graham Hukill'})

# 	return "The results of {PID} objectBag exporting...".format(PID=self.pid)