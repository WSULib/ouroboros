
# Ouroboros config
import localConfig

# import logging
from WSUDOR_ContentTypes import logging
logging = logging.getChild("LMDB_ENV")

# init LMDB
import lmdb
lmdb_env = lmdb.open(localConfig.LMDB_DB_LOCATION)