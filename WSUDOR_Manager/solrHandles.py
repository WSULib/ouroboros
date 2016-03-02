from mysolr import Solr
import requests
import localConfig

# set connection through requests
session = requests.Session()

# Core used for search and retrieval (e.g. powers front-end API)
try:
	# single, primary search core
	solr_handle = Solr('http://localhost/solr4/%s' % (localConfig.SOLR_SEARCH_CORE), make_request=session)

	# Core used for bookreader fulltext
	solr_bookreader_handle = Solr('http://localhost/solr4/%s' % (localConfig.SOLR_BOOKREADER_CORE), make_request=session)
except:
	print "Could not setup solr handles"
	solr_handle = False
	solr_bookreader_handle = False


