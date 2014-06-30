# small utility to edit RELS-EXT datastream for objects

# handles
from fedoraManager2.solrHandles import solr_handle
from fedoraManager2.fedoraHandles import fedora_handle


def editRELS(job_package):
	PID= job_package['PID']		
	obj_ohandle = fedora_handle.get_object(PID)		

	isMemberOfCollection = 'info:fedora/fedora-system:def/relations-external#isMemberOfCollection'
	collection_uri = 'info:fedora/testing:collection'
	obj_ohandle.add_relationship(isMemberOfCollection, collection_uri)