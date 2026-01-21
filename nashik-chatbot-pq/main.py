"""
Main FastAPI Application
Thar Roxx Quality Intelligence API
"""

import logging
from fastapi.staticfiles import StaticFiles
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.endpoints import router as api_router
from app.config.config import get_settings

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

    # Include API routes first
    app.include_router(api_router, prefix="/api")

    # Determine frontend build directory
    import sys
    from pathlib import Path
    from fastapi.responses import FileResponse
    
    def get_frontend_path():
        # 1. Check current working directory (e.g., ./frontend/build)
        cwd_path = Path.cwd() / "frontend" / "build"
        if cwd_path.exists():
            return cwd_path
            
        # 2. If frozen, check next to executable
        if getattr(sys, 'frozen', False):
            exe_path = Path(sys.executable).parent / "frontend" / "build"
            if exe_path.exists():
                return exe_path
                
            # 3. If frozen (onefile), check temp dir (sys._MEIPASS)
            if hasattr(sys, '_MEIPASS'):
                 meipass_path = Path(sys._MEIPASS) / "frontend" / "build"
                 if meipass_path.exists():
                     return meipass_path

        # 4. Fallback to default dev path
        return Path("./frontend/build")

    frontend_path = get_frontend_path()
    
    if frontend_path.exists():
        # 1. Mount /static explicitly (CSS/JS chunks)
        static_dir = frontend_path / "static"
        if static_dir.exists():
            app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
        
        # 2. Catch-all route for SPA
        # This serves files if they exist (favicon.ico, etc.), otherwise index.html
        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str):
            # Check if actual file exists in build dir
            file_path = frontend_path / full_path
            if file_path.is_file():
                return FileResponse(file_path)
            
            # Otherwise serve index.html (client-side routing)
            return FileResponse(frontend_path / "index.html")
    else:
        logger.warning(f"⚠️ Frontend build not found at {frontend_path}. UI will not be available.")

    return app


app = create_app()

if __name__ == "__main__":
    import sys
    settings = get_settings()

    # Configure uvicorn with optimized settings for Windows
    # Check if frozen to determine how to pass the app
    is_frozen = getattr(sys, 'frozen', False)
    
    run_config = {
        "host": settings.SERVER_HOST,
        "port": settings.SERVER_PORT,
        "log_level": settings.SERVER_LOG_LEVEL.lower(),
        "workers": 1,
    }

    if is_frozen:
        # Frozen: Pass app object, disable reload
        run_config["app"] = app
        run_config["reload"] = False
        logger.info("❄️ Running in frozen mode")
    else:
        # Dev: Pass import string, enable reload from settings
        run_config["app"] = "main:app"
        run_config["reload"] = settings.SERVER_RELOAD
    
    # When reload is enabled (and not frozen), add reload-specific settings
    if run_config.get("reload"):
        run_config.update(
            {
                "reload_dirs": ["app", "backend"],
                "reload_delay": 0.5,
            }
        )

    uvicorn.run(**run_config)
