"""
Vennela AI - Main Entry Point
Wrapper to ensure compatibility with Render/production deployments.
"""

from app import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)