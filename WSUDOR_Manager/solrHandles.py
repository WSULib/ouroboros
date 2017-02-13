from mysolr import Solr
import requests
import localConfig

# set connection through requests
# session = requests.Session()

# Core used for search and retrieval (e.g. powers front-end API)
# single, primary search core
solr_handle = Solr('http://localhost/solr4/%s' % (localConfig.SOLR_SEARCH_CORE), version=4)
# Core used for bookreader fulltext
solr_bookreader_handle = Solr('http://localhost/solr4/%s' % (localConfig.SOLR_BOOKREADER_CORE), version=4)
# Core used for WSUDOR user accounts
solr_user_handle = Solr('http://localhost/solr4/users', version=4)


def onDemand(core):
    return Solr('http://localhost/solr4/%s' % (core), version=4)
