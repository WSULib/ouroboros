from mysolr import Solr
import requests
import localConfig

# set connection through requests
session = requests.Session()

# Core used for search and retrieval (e.g. powers front-end API)
solr_handle = Solr('http://silo.lib.wayne.edu/solr4/{SOLR_SEARCH_CORE}'.format(SOLR_SEARCH_CORE=localConfig.SOLR_SEARCH_CORE, make_request=session))

# Core used for management, indexing, deletion
solr_manage_handle = Solr('http://silo.lib.wayne.edu/solr4/{SOLR_MANAGE_CORE}'.format(SOLR_MANAGE_CORE=localConfig.SOLR_MANAGE_CORE, make_request=session))

