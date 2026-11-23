"""Workers entrypoint: wire the portable FastAPI app to the ASGI adapter.

D1 + workers.fetch are injected per request via app.api.deps (scope env).
"""

from app.main import create_app
from workers.asgi import entrypoint

Default = entrypoint(create_app(platform="workers"))
