nohup celery worker -A cl.cl --loglevel=Info --concurrency=4 & > celery.out
nohup python runserver.py & > fm2_server.out
