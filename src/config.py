import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Define Base Paths
BASE_DIR = os.getenv("PROJECT_ROOT_DIR", Path(__file__).parent.parent)
SOURCE_DIR = BASE_DIR / "data_source"
CLEANED_DIR = BASE_DIR / "data_cleaned"

# Ensure output directory exists
CLEANED_DIR.mkdir(parents=True, exist_ok=True)

# InsForge Database URI (to be added to .env later)
DATABASE_URI = os.getenv("INSFORGE_DB_URI")