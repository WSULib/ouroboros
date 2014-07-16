from __future__ import absolute_import

from celery import Celery

# instantiate Celery object
celery = Celery(backend='redis://localhost:6379/1',include=[
                         'fedoraManager2.actions.actions'                         
                        ])

# import celery config file
celery.config_from_object('celeryconfig')

if __name__ == '__main__':
    celery.start()