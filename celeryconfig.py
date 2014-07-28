from localConfig import *

# RabbitMQ
# BROKER_URL = 'amqp://guest:guest@mitten:5672//'

# Redis
BROKER_URL='redis://localhost:6379/{redis_broker_db}'.format(redis_broker_db=str(redis_broker_db))
RESULT_BACKEND='redis://localhost:6379/{redis_backend_db}'.format(redis_backend_db=str(redis_backend_db))
RESULT_SERIALIZER='json'


