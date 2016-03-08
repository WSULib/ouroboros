#export C_FORCE_ROOT="true"
/usr/local/lib/venvs/ouroboros/bin/celery worker -A cl.cl --loglevel=Info --concurrency=1
