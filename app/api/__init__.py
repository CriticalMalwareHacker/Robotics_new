"""New additive API routers (parking robot). Mounted from app/main.py."""

from .hud_routes import router as hud_router
from .parking_routes import router as parking_router
from .robot_routes import router as robot_router

__all__ = ["hud_router", "parking_router", "robot_router"]
