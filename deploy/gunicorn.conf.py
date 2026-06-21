"""Gunicorn settings for the component tracker (production server on Proxmox).

Two gthread workers are plenty for a personal tool and keep memory tiny, while
giving a little concurrency without spawning many processes that contend over
the single SQLite file. Logs go to stdout/stderr so journald/systemd captures
them (view with: journalctl -u component-tracker -f).
"""

bind = "0.0.0.0:8000"
workers = 2
threads = 4
worker_class = "gthread"
timeout = 60
graceful_timeout = 30
accesslog = "-"
errorlog = "-"
loglevel = "info"
