"""
Entry point for the Nashik Chatbot Application.
Handles CLI interactions (Data Loading) before starting the server.
"""

import sys
import logging
import uvicorn
from app.config.config import get_settings
from main import app  # Import the FastAPI app instance

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

def interactive_startup():
    """
    Handles the interactive command-line startup process.
    Asks the user if they want to load data.
    """
    print("\n" + "=" * 70)
    print("      Thar Roxx Quality Intelligence API - Startup      ")
    print("=" * 70)
    
    try:
        should_load = input("\nDo you want to load data before starting the server? (y/n): ").strip().lower()
    except EOFError:
        # Handle cases where input is not available (e.g. non-interactive mode)
        should_load = 'n'

    if should_load in ['y', 'yes']:
        folder_path = input("Enter the folder path containing CSV files: ").strip()
        # Remove quotes if user copied path as "C:\path"
        folder_path = folder_path.strip('"').strip("'")
        
        from pathlib import Path
        if Path(folder_path).exists():
            print("\n" + "!" * 80)
            print("⚠️  WARNING: Data loading process starting...")
            print("⏳ This may take 30 minutes to 1 hour depending on dataset size and connection.")
            print("☕ Please be patient and do not close this window.")
            print("!" * 80 + "\n")
            
            try:
                from app.services.data_loader import load_data
                load_data(folder_path)
                print("\n✅ Data loading process finished.")
            except Exception as e:
                print(f"\n❌ Data loading failed: {e}")
                input("Press Enter to continue to server startup (or Ctrl+C to exit)...")
        else:
            print(f"\n❌ Error: Folder not found at '{folder_path}'")
            input("Press Enter to continue to server startup...")
    
    print("\n🚀 Starting server...")
    start_server()

def start_server():
    """
    Configures and starts the Uvicorn server.
    """
    settings = get_settings()

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
        # Important: When using 'app' object, we pass it directly
        run_config["app"] = app 
        run_config["reload"] = False
        logger.info("❄️ Running in frozen mode")
    else:
        # Dev: Pass import string, enable reload from settings
        # Note: Since we are in run.py, "main:app" still refers to app object in main.py
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

if __name__ == "__main__":
    interactive_startup()
