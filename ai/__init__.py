"""
AI Routing System
Pluggable routing algorithms for autonomous sailing.
"""

from ai.base_router import BaseRouter, RoutingContext
from ai.router_factory import create_router, list_routers, register_router

__all__ = [
    'BaseRouter',
    'RoutingContext',
    'create_router',
    'list_routers',
    'register_router',
]
