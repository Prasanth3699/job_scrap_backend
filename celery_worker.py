import os
import sys
from pathlib import Path

# Add the project root directory to Python path
project_root = str(Path(__file__).parent)
sys.path.insert(0, project_root)

from app import celery_app

if __name__ == "__main__":
    celery_app.start()
