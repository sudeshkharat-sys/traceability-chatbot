"""
API Router Aggregator
Combines all route modules
"""

from fastapi import APIRouter
from backend.api.routes.conversations import conversation_routes
from backend.api.routes.health import health_routes
from backend.api.routes.auth import auth_routes
from backend.api.routes.part_labeler_routes import router as part_labeler_router
# Create main router
router = APIRouter()

# Include sub-routers
router.include_router(
    conversation_routes.router, prefix="/conversations", tags=["conversations"]
)

router.include_router(health_routes.router, prefix="", tags=["health"])

router.include_router(auth_routes.router, prefix="/auth", tags=["auth"])

router.include_router(part_labeler_router, prefix="/part-labeler", tags=["part_labeler"])
