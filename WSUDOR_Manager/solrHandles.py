from mysolr import Solr
import requests
import localConfig

# Solr handles

# single, primary search core
solr_handle = Solr('%s/%s' % (localConfig.SOLR_ROOT, localConfig.SOLR_MANAGE_CORE), version=4)
# Core used for bookreader fulltext
solr_bookreader_handle = Solr('%s/%s' % (localConfig.SOLR_ROOT, localConfig.SOLR_BOOKREADER_CORE), version=4)
# Core used for WSUDOR user accounts
solr_user_handle = Solr('%s/users' % (localConfig.SOLR_ROOT), version=4)

def onDemand(core):
    return Solr('%s/%s' % (localConfig.SOLR_ROOT, core), version=4)
