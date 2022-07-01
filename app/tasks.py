import json
import os
import requests
import hashlib

from io import BytesIO
from celery.utils.log import get_task_logger
from minio import Minio
from minio.error import BucketAlreadyExists, BucketAlreadyOwnedByYou, NoSuchKey
from worker import app


logger = get_task_logger(__name__)


@app.task(bind=True, name='refresh')
def refresh(self, urls):
    """
    The task that triggers API requests
    :url: request URL
    """
    for url in urls:
        get_metric.s(url).delay()


@app.task(bind=True, name='get_metric')
def get_metric(self, url):
    """
    Make API requests to get metrics
    :url: request URL
    """
    metric = {}
    logger.info(f'request: {url}')
    metric_name = url.split('/')[-1]
    api_key = os.environ['SAMSARA_API_KEY']
    data = {"sensors": [os.environ['SENSOR_ID']]}
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    response = requests.post(url, headers=headers, data=json.dumps(data))
    sensor_data = response.json().get('sensors')[-1]
    if metric_name == 'humidity':
        metric[metric_name] = sensor_data.get('humidity')
        metric['time'] = sensor_data.get('humidityTime')
    else:
        metric[metric_name] = sensor_data.get('ambientTemperature')
        metric['time'] = sensor_data.get('ambientTemperatureTime')
    logger.info(metric)
    save_metric.s('data', metric_name, metric).delay()


@app.task(bind=True, name='save_metric', queue='minio')
def save_metric(self, bucket, key, metric):
    """
    Save API metrics to object storage
    :bucket: bucket name
    :key: file name
    :metric: metric data
    """
    metric_json = json.dumps(metric)
    key_timestamp = f"{key}_{metric['time']}"
    minio_client = Minio(os.environ['MINIO_HOST'],
                         access_key=os.environ['MINIO_ACCESS_KEY'],
                         secret_key=os.environ['MINIO_SECRET_KEY'],
                         secure=False)

    try:
        minio_client.make_bucket(bucket)
    except BucketAlreadyExists:
        pass
    except BucketAlreadyOwnedByYou:
        pass
    hexdigest = hashlib.md5(metric_json.encode()).hexdigest()
    try:
        st = minio_client.stat_object(bucket, key_timestamp)
        update = st.etag != hexdigest
    except NoSuchKey as err:
        update = True

    if update:
        logger.info(f'Write {bucket}/{key_timestamp} to minio')
        stream = BytesIO(metric_json.encode())
        minio_client.put_object(bucket, key_timestamp, stream, stream.getbuffer().nbytes)
