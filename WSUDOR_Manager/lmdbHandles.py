
# Ouroboros config
import localConfig

# import logging
from WSUDOR_ContentTypes import logging
logging = logging.getChild("LMDB_ENV")

# init LMDB
import lmdb
'''
multiples of 4096 for map_size (40960000 ~ 40mb)
'''
lmdb_env = lmdb.open(localConfig.LMDB_DB_LOCATION, map_size=localConfig.LMDB_MAP_SIZE)
