from WSUDOR_Manager import *
fedora_handle = fedoraHandles.fedora_handle
try:
	solr_handle = solrHandles.solr_handle
	solr_manage_handle = solrHandles.solr_manage_handle
	solr_bookreader_handle = solrHandles.solr_bookreader_handle
except:
	print "Could not load solr handles, skipping."
