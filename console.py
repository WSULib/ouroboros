print "importing WSUDOR_Manager"
from WSUDOR_Manager import *

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