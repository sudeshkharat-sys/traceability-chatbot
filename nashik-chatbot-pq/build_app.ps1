# Build script for Nashik Chatbot

$ErrorActionPreference = "Stop"

Write-Host "Checking for frontend build..."
if (Test-Path "frontend/build") {
    Write-Host "✅ Frontend build found."
} else {
    Write-Host "⚠️  Frontend build NOT found in 'frontend/build'. The EXE will verify this at runtime."
}

Write-Host "Building EXE with PyInstaller..."

# Define the PyInstaller command
$pyinstallerArgs = @(
    "--noconfirm",
    "--onedir",
    "--console",
    "--name", "NashikChatbot",
    "--clean",
    "--collect-all", "uvicorn",
    "--collect-all", "fastapi",
    "--collect-all", "app",
    "--collect-all", "backend",
    "--hidden-import", "uvicorn.logging",
    "--hidden-import", "uvicorn.loops",
    "--hidden-import", "uvicorn.loops.auto",
    "--hidden-import", "uvicorn.protocols",
    "--hidden-import", "uvicorn.protocols.http",
    "--hidden-import", "uvicorn.protocols.http.auto",
    "--hidden-import", "uvicorn.lifespan",
    "--hidden-import", "uvicorn.lifespan.on",
    "--paths", ".",
    "run.py"
)

# Check if we can run via conda
if (Get-Command "conda" -ErrorAction SilentlyContinue) {
    Write-Host "Using conda environment 'env'..."
    conda run -n env pyinstaller @pyinstallerArgs
} else {
    Write-Host "Conda not found in PATH. Trying to run pyinstaller directly..."
    pyinstaller @pyinstallerArgs
}

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Build successful."
    
    # Post-build: Copy .env
    $distDir = "dist/NashikChatbot"
    if (Test-Path "app/config/.env") {
        Write-Host "Copying .env to dist folder..."
        Copy-Item "app/config/.env" -Destination "$distDir/.env"
    }
    
    # Post-build: Copy frontend/build
    if (Test-Path "frontend/build") {
        Write-Host "Copying frontend/build to dist folder..."
        New-Item -ItemType Directory -Force -Path "$distDir/frontend" | Out-Null
        Copy-Item "frontend/build" -Destination "$distDir/frontend" -Recurse
    }
    
    Write-Host "🎉 Distribution ready in $distDir"
} else {
    Write-Host "❌ Build failed."
    exit 1
}
