from flask import request
from prometheus_client import Counter, Gauge
import time
import psutil
import socket

# Get the host name of the machine
host = socket.gethostname()

REQUEST_COUNT = Counter(
    'request_count', 'App Request Count',
    ['app_name', 'host', 'endpoint', 'http_status'])

REQUEST_LATENCY = Gauge('request_latency_seconds', 'Request latency',
                            ['app_name', 'host', 'endpoint'])

CPU_USAGE = Gauge('cpu_usage_percent', 'CPU Usage Percent',
                            ['app_name', 'host', 'endpoint'])

MEM_USAGE = Gauge('mem_usage_mbytes', 'Memory Usage in MB',
                            ['app_name', 'host', 'endpoint'])

methods = ['metrics', 'detect']


def start_timer():
    if any(item == request.endpoint for item in methods):
        request.start_time = time.time()


def stop_timer(response):
    if any(item == request.endpoint for item in methods):
        resp_time = time.time() - request.start_time
        REQUEST_LATENCY.labels('face_detect', host, request.endpoint).set(resp_time)

        #for c, p in enumerate(psutil.cpu_percent(interval=0, percpu=True)):
        p = psutil.cpu_percent(0)
        CPU_USAGE.labels('face_detect', host, request.endpoint).set(p)

        m = psutil.virtual_memory()
        MEM_USAGE.labels('face_detect', host, request.endpoint).set(m.used/1000000.0)
    return response


def record_request_data(response):
    if any(item == request.endpoint for item in methods):
        REQUEST_COUNT.labels('face_detect', host, request.endpoint,
                             response.status_code).inc()
    return response


def setup_metrics(app):
    app.before_request(start_timer)
    # The order here matters since we want stop_timer
    # to be executed first
    app.after_request(record_request_data)
    app.after_request(stop_timer)
