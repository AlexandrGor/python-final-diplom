import os

from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'orders.settings')

CELERY_BACKEND = os.getenv('CELERY_BACKEND')
CELERY_BROKER = os.getenv('CELERY_BROKER')

app = Celery('orders', backend=CELERY_BACKEND, broker=CELERY_BROKER)

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
# например, параметр task_always_eager становится CELERY_TASK_ALWAYS_EAGER, а параметр Broker_url становится CELERY_BROKER_URL
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
# С помощью строки ниже Celery автоматически обнаружит все файлы tasks.py из всех установленных приложений.
# This way you don’t have to manually add the individual modules to the CELERY_IMPORTS setting.
app.autodiscover_tasks()

# debug_task — это задача, которая выводит информацию о своем запросе.
# Это использует новую опцию задачи bind=True, представленную в Celery 3.1,
# чтобы легко ссылаться на текущий экземпляр задачи.
@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')