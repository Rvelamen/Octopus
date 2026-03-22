"""Entry point for PyInstaller packaged Octopus backend."""

from backend.api.server import app, PORT
import uvicorn
import os

if __name__ == "__main__":
    port = int(os.environ.get("OCTOPUS_PORT", PORT))
    uvicorn.run(app, host="0.0.0.0", port=port)