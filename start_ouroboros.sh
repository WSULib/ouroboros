nohup celery worker -A cl.cl --loglevel=Info --concurrency=2 & > celery.out
nohup python runserver.py & > ouroboros_server.out
