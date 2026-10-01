"""New additive API routers (parking robot). Mounted from app/main.py."""

from .parking_routes import router as parking_router

__all__ = ["parking_router"]
