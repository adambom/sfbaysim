"""
Router Factory
Creates routing algorithm instances by name using registry pattern.
"""

from typing import Dict, Any, List
from ai.base_router import BaseRouter


# Global router registry (like SCENARIOS in config.py)
_ROUTERS: Dict[str, type] = {}


def register_router(name: str, router_class: type):
    """
    Register a router implementation.

    Args:
        name: Router identifier (e.g., 'vmg', 'astar')
        router_class: Router class (subclass of BaseRouter)
    """
    _ROUTERS[name] = router_class


def create_router(name: str, config: Dict[str, Any] = None) -> BaseRouter:
    """
    Create router instance by name.

    Args:
        name: Router identifier
        config: Optional configuration dict

    Returns:
        BaseRouter instance

    Raises:
        ValueError: If router name not found
    """
    if name not in _ROUTERS:
        raise ValueError(f"Unknown router: '{name}'. Available: {list(_ROUTERS.keys())}")

    router_class = _ROUTERS[name]
    return router_class(config)


def list_routers() -> List[str]:
    """
    List available router names.

    Returns:
        List of registered router names
    """
    return list(_ROUTERS.keys())


# ===== ROUTER REGISTRATION =====
# Import and register available routers

# Simple routers (always available)
try:
    from ai.simple.greedy_vmg import GreedyVMGRouter
    register_router('vmg', GreedyVMGRouter)
except ImportError as e:
    print(f"Warning: Could not load Greedy VMG router: {e}")

# Advanced routers (optional)
try:
    from ai.advanced.astar_router import AStarRouter
    register_router('astar', AStarRouter)
except ImportError:
    pass  # A* not implemented yet

try:
    from ai.advanced.isochrone_router import IsochroneRouter
    register_router('isochrone', IsochroneRouter)
except ImportError:
    pass  # Isochrone not implemented yet
