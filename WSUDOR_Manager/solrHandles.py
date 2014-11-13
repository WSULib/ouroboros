from mysolr import Solr
import requests

# set connection through requests
session = requests.Session()
solr_handle = Solr('http://silo.lib.wayne.edu/solr4/search', make_request=session)

