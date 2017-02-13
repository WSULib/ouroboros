from mysolr import Solr
import requests
import localConfig

# Core used for search and retrieval (e.g. powers front-end API)
try:
	# single, primary search core
	solr_handle = Solr('http://localhost/solr4/%s' % (localConfig.SOLR_SEARCH_CORE))
	# Core used for bookreader fulltext
	solr_bookreader_handle = Solr('http://localhost/solr4/%s' % (localConfig.SOLR_BOOKREADER_CORE))
	# Core used for WSUDOR user accounts
	solr_user_handle = Solr('http://localhost/solr4/users')
except:
	print "Could not setup solr handles"
	solr_handle = False
	solr_bookreader_handle = False


def onDemand(core):
	try:
		return Solr('http://localhost/solr4/%s' % (core))
	except:
		return False
