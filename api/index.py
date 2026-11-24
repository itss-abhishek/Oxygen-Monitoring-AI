import os
import sys

# Ensure project root is in Python sys.path for backend imports
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.app import app

# Vercel Serverless Function entrypoint
# Vercel's @vercel/python runtime automatically binds to the module-level 'app' WSGI callable
app = app

if __name__ == "__main__":
    app.run()
