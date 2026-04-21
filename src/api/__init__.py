"""FastAPI HTTP layer — serves the LangGraph agent behind a stateless HTTP API.

This package is a thin translation layer: it accepts JSON requests over HTTP,
invokes the compiled graph, and returns the assistant's reply. All business
logic continues to live in :mod:`src.graph`.
"""
