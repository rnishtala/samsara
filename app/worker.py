import os
from celery import Celery


app = Celery(include=('tasks',))
app.conf.beat_schedule = {
    'refresh': {
        'task': 'refresh',
        'schedule': float(os.environ['SCHEDULE']),
        'args': (os.environ['ENDPOINTS'].split(','),)
    },
}
