"""Business logic layer.

Routers stay thin: parse, delegate, serialise. The rules live here so they can
be tested without HTTP, and so the seed script exercises the same code paths
the API does rather than a parallel implementation that can drift.
"""
