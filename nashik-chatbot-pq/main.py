"""
Main FastAPI Application
Thar Roxx Quality Intelligence API
"""

import logging
from fastapi.staticfiles import StaticFiles
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from backend.api.endpoints import router as api_router
from app.config.config import get_settings
from fastapi.templating import Jinja2Templates

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager
    Handles startup and shutdown events
    """
    # ========== STARTUP ==========
    logger.info("🚀 Application starting up...")

    try:
        # Run all initialization: database, tables, prompts, connections
        from app.services.startup_initializer import run_startup_initialization

        results = run_startup_initialization(skip_on_error=True)

        # Store results in app state for health checks
        app.state.initialization_results = results
        app.state.is_initialized = all(r["success"] for r in results.values())

        if app.state.is_initialized:
            logger.info("✅ Application initialized successfully")
        else:
            logger.warning("⚠️  Application started with some initialization failures")

    except Exception as e:
        logger.error(f"❌ Critical error during startup: {e}")
        app.state.initialization_results = {"error": str(e)}
        app.state.is_initialized = False

    yield  # Application is running

    # ========== SHUTDOWN ==========
    logger.info("🛑 Application shutting down...")

    # Cleanup connections
    try:
        from app.connectors.neo4j_connector import Neo4jConnector

        neo4j = Neo4jConnector()
        neo4j.close()
        logger.info("✅ Neo4j connection closed")
    except Exception as e:
        logger.warning(f"⚠️  Error closing Neo4j connection: {e}")

    logger.info("👋 Application shutdown complete")


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application

    Returns:
        Configured FastAPI instance
    """
    settings = get_settings()
    app = FastAPI(
        title="Thar Roxx Quality Intelligence API",
        description="Neo4j-powered automotive quality and traceability analysis system",
        version="1.0.0",
        docs_url="/docs",
        lifespan=lifespan,  # Register lifespan manager for startup/shutdown
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.mount("/", StaticFiles(directory="./frontend", html=True), name="static")
    app.include_router(api_router, prefix="/api")
    return app


app = create_app()

templates = Jinja2Templates(directory="templates")

@app.get("/")
async def serve_spa(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

if __name__ == "__main__":
    settings = get_settings()

    # Configure uvicorn with optimized settings for Windows
    config = {
        "app": "main:app",
        "host": settings.SERVER_HOST,
        "port": settings.SERVER_PORT,
        "reload": settings.SERVER_RELOAD,
        "log_level": settings.SERVER_LOG_LEVEL.lower(),
        "workers": 1,  # Single worker to avoid multiprocessing issues on Windows
    }

    # When reload is enabled, add reload-specific settings
    if settings.SERVER_RELOAD:
        config.update(
            {
                "reload_dirs": ["app", "backend"],  # Only watch relevant directories
                "reload_delay": 0.5,  # Add small delay to batch changes
            }
        )

    uvicorn.run(**config)
