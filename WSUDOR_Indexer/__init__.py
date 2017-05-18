# setup logging for WSUDOR_Indexer
from localConfig import logging, LOGGING_STREAM, LOGGING_LEVEL
logging.basicConfig(stream=LOGGING_STREAM, level=LOGGING_LEVEL)
logging = logging.getLogger('WSUDOR_Indexer')

# import models
import models