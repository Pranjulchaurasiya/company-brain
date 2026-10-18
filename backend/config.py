import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

FALKORDB_HOST = os.getenv("FALKORDB_HOST", "127.0.0.1")
FALKORDB_PORT = int(os.getenv("FALKORDB_PORT", "6380"))
FALKORDB_GRAPH_NAME = os.getenv("FALKORDB_GRAPH_NAME", "company_brain")
DEFAULT_WORKSPACE_ID = os.getenv("WORKSPACE_ID", "ws_company_prime")

SERVER_HOST = os.getenv("HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("PORT", "8000"))
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# Paths
FIXTURES_DIR = ROOT_DIR / "fixtures" / "payments"
