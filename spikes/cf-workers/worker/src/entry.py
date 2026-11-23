"""Cloudflare Workers entrypoint: hand the portable FastAPI app to the ASGI adapter."""

from spike_app import app
from workers.asgi import entrypoint

Default = entrypoint(app)
