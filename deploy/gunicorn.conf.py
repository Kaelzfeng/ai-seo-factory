# Gunicorn configuration
import os
bind = os.getenv("GUNICORN_BIND", "127.0.0.1:8000")
workers = int(os.getenv("GUNICORN_WORKERS", "4"))
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))
accesslog = os.getenv("GUNICORN_ACCESS_LOG", "logs/gunicorn-access.log")
errorlog = os.getenv("GUNICORN_ERROR_LOG", "logs/gunicorn-error.log")
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
wsgi_app = "app:app"
