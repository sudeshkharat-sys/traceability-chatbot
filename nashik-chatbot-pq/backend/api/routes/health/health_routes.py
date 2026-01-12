"""
Health Check API Routes
System health and status endpoints
"""

import logging
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from app.connectors.neo4j_connector import Neo4jConnector
from app.connectors.state_db_connector import StateDBConnector

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """
    Basic health check endpoint

    Returns:
        Service status
    """
    return JSONResponse(
        {"status": "healthy", "service": "Thar Roxx Quality Intelligence API"}
    )


@router.get("/health/detailed")
async def detailed_health_check():
    """
    Detailed health check with database connectivity

    Returns:
        Detailed system status
    """
    try:
        # Check Neo4j
        neo4j_status = "unknown"
        neo4j_error = None
        try:
            neo4j = Neo4jConnector()
            if neo4j.test_connection():
                neo4j_status = "connected"
            else:
                neo4j_status = "disconnected"
        except Exception as e:
            neo4j_status = "error"
            neo4j_error = str(e)

        # Check PostgreSQL
        postgres_status = "unknown"
        postgres_error = None
        try:
            state_db = StateDBConnector()
            if state_db.test_connection():
                postgres_status = "connected"
            else:
                postgres_status = "disconnected"
        except Exception as e:
            postgres_status = "error"
            postgres_error = str(e)

        overall_status = (
            "healthy"
            if neo4j_status == "connected" and postgres_status == "connected"
            else "degraded"
        )

        response = {
            "status": overall_status,
            "service": "Thar Roxx Quality Intelligence API",
            "components": {
                "neo4j": {"status": neo4j_status, "error": neo4j_error},
                "postgresql": {"status": postgres_status, "error": postgres_error},
            },
        }

        return JSONResponse(response)

    except Exception as e:
        logger.error(f"Error in detailed health check: {e}")
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


@router.get("/stats")
async def get_stats():
    """
    Get system statistics

    Returns:
        System statistics
    """
    try:
        neo4j = Neo4jConnector()

        stats = {
            "neo4j": {
                "parts": neo4j.get_node_count("Part"),
                "vehicles": neo4j.get_node_count("Vehicle"),
                "warranty_claims": neo4j.get_node_count("WarrantyClaim"),
                "batches": neo4j.get_node_count("Batch"),
                "vendors": neo4j.get_node_count("Vendor"),
            }
        }

        return JSONResponse({"stats": stats})

    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/initialization")
async def get_initialization_status(request: Request):
    """
    Get application initialization status

    Returns:
        Initialization results from startup
    """
    try:
        # Get initialization results from app state
        is_initialized = getattr(request.app.state, "is_initialized", False)
        results = getattr(request.app.state, "initialization_results", {})

        return JSONResponse(
            {
                "initialized": is_initialized,
                "results": {
                    k: {
                        "success": v.get("success", False),
                        "message": v.get("message", ""),
                    }
                    for k, v in results.items()
                },
            }
        )

    except Exception as e:
        logger.error(f"Error getting initialization status: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/prompts")
async def list_prompts():
    """
    List all system prompts from database

    Returns:
        List of prompts with metadata
    """
    try:
        from app.services.prompt_manager import get_prompt_manager

        manager = get_prompt_manager()
        prompts = manager.get_all_prompts()

        # Return prompt metadata (not full content for performance)
        prompt_list = []
        for key, data in prompts.items():
            prompt_list.append(
                {
                    "key": key,
                    "name": data["name"],
                    "updated_at": (
                        str(data["updated_at"]) if data.get("updated_at") else None
                    ),
                    "content_length": (
                        len(data["content"]) if data.get("content") else 0
                    ),
                }
            )

        return JSONResponse({"prompts": prompt_list, "count": len(prompt_list)})

    except Exception as e:
        logger.error(f"Error listing prompts: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/prompts/{prompt_key}")
async def get_prompt(prompt_key: str):
    """
    Get a specific prompt by key

    Args:
        prompt_key: The unique key for the prompt

    Returns:
        Prompt content and metadata
    """
    try:
        from app.services.prompt_manager import get_prompt_manager

        manager = get_prompt_manager()
        prompts = manager.get_all_prompts()

        if prompt_key not in prompts:
            return JSONResponse(
                {"error": f"Prompt '{prompt_key}' not found"}, status_code=404
            )

        data = prompts[prompt_key]

        return JSONResponse(
            {
                "key": prompt_key,
                "name": data["name"],
                "updated_at": (
                    str(data["updated_at"]) if data.get("updated_at") else None
                ),
                "content": data["content"],
            }
        )

    except Exception as e:
        logger.error(f"Error getting prompt {prompt_key}: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)
