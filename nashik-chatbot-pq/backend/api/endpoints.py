"""
API Router Aggregator
Combines all route modules
"""

from fastapi import APIRouter
from backend.api.routes.conversations import conversation_routes
from backend.api.routes.health import health_routes

# Create main router
router = APIRouter()

# Include sub-routers
router.include_router(
    conversation_routes.router, prefix="/conversations", tags=["conversations"]
)

router.include_router(health_routes.router, prefix="", tags=["health"])
