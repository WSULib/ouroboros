export C_FORCE_ROOT="true"
celery worker -A cl.cl --loglevel=Info --concurrency=2
