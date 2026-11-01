"""
Entrypoint Vercel (zero-config FastAPI): Vercel mencari objek `app` di app.py.
Aplikasi sebenarnya ada di web_app/main.py.
"""
from web_app.main import app  # noqa: F401
