from localConfig import *

# http://docs.celeryproject.org/en/latest/userguide/configuration.html#std:setting-accept_content

# Redis
BROKER_URL='redis://localhost:6379/{REDIS_BROKER_DB}'.format(REDIS_BROKER_DB=str(REDIS_BROKER_DB))
RESULT_BACKEND='redis://localhost:6379/{REDIS_BACKEND_DB}'.format(REDIS_BACKEND_DB=str(REDIS_BACKEND_DB))
RESULT_SERIALIZER='json'
CELERY_ACCEPT_CONTENT = ['json','pickle']
CELERYD_HIJACK_ROOT_LOGGER = False

# Can this log to stdout?