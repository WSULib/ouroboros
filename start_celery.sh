#export C_FORCE_ROOT="true"
/usr/local/lib/venvs/ouroboros/bin/celery worker -A WSUDOR_Manager.celery --loglevel=Info --concurrency=1
