import sys
from pathlib import Path
import uvicorn
from fastapi.staticfiles import StaticFiles

# Add src to pythonpath
sys.path.insert(0, str(Path(__file__).parent / "src"))

from webrag.api.server import app

# Mount built frontend dist if available
frontend_dist = Path(__file__).parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")

if __name__ == "__main__":
    print("\n" + "=" * 65)
    print("  WebRAG: The Reading Room — Live Server")
    print("  API running on:       http://localhost:8000/api")
    if frontend_dist.exists():
        print("  Web App running on:   http://localhost:8000")
    print("=" * 65 + "\n")
    uvicorn.run(app, host="127.0.0.1", port=8000)
