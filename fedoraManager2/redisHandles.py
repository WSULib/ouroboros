import redis


# redis handle
r_broker = redis.StrictRedis(host='localhost', port=6379, db=1)
r_job_handle = redis.StrictRedis(host='localhost', port=6379, db=2)
r_selectedPIDs_handle = redis.StrictRedis(host='localhost', port=6379, db=3)
r_PIDlock = redis.StrictRedis(host='localhost', port=6379, db=4)


