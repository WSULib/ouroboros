import redis
from localConfig import *

# redis handle
r_broker = redis.StrictRedis(host='localhost', port=6379, db=REDIS_BROKER_DB)
r_backend = redis.StrictRedis(host='localhost', port=6379, db=REDIS_BACKEND_DB)
r_job_handle = redis.StrictRedis(host='localhost', port=6379, db=2)
r_selectedPIDs_handle = redis.StrictRedis(host='localhost', port=6379, db=3)
r_PIDlock = redis.StrictRedis(host='localhost', port=6379, db=4)