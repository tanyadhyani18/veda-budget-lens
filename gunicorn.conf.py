"""Gunicorn settings. Gunicorn reads this file automatically, so the plain start
command `gunicorn app:app` works on Render with the right timeout and workers.

One worker is deliberate: the short-lived analysis memory and the AI usage limits
live in the server's memory. Four threads still let several visitors use the app.
120 seconds covers the worst case of two slow AI attempts (2 x 30 s) plus margin.
"""
import os

bind = f"0.0.0.0:{os.environ.get('PORT', '5000')}"
workers = 1
threads = 4
timeout = 120
