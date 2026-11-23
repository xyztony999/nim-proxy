"""NIM Proxy — OpenAI-compatible relay for NVIDIA NIM with an admin console.

Dual-target: self-hosted server (uvicorn + SQLite) and Cloudflare Workers
(Python Workers + D1). Platform differences live in composition roots and
adapters; business code (services/schemas) is platform-agnostic.
"""
