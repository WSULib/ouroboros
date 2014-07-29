import redis
from localConfig import *


# redis handle
r_broker = redis.StrictRedis(host='localhost', port=6379, db=redis_broker_db)
r_backend = redis.StrictRedis(host='localhost', port=6379, db=redis_backend_db)
r_job_handle = redis.StrictRedis(host='localhost', port=6379, db=2)
r_selectedPIDs_handle = redis.StrictRedis(host='localhost', port=6379, db=3)
r_PIDlock = redis.StrictRedis(host='localhost', port=6379, db=4)