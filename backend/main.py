import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import DEFAULT_WORKSPACE_ID, SERVER_HOST, SERVER_PORT
from backend.db.falkordb_client import db_client
from backend.ingestion.importer import import_all_fixtures
from backend.api.routes import router

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("company_brain.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure graph schema & preload synthetic dataset for instant zero-login judge experience
    logger.info("Initializing Company Brain on FalkorDB...")
    try:
        health = db_client.check_health()
        logger.info(f"FalkorDB Health: {health['status']}")
        # Check if graph has nodes; if empty, preload
        g = db_client.get_graph()
        rows = g.query("MATCH (n {workspace_id: $ws}) RETURN count(n)", {"ws": DEFAULT_WORKSPACE_ID}).result_set
        if not rows or rows[0][0] == 0:
            logger.info("Empty graph detected. Seeding synthetic company fixtures...")
            import_all_fixtures(workspace_id=DEFAULT_WORKSPACE_ID)
        else:
            logger.info(f"Existing graph found with {rows[0][0]} nodes.")
    except Exception as e:
        logger.error(f"Error during startup graph initialization: {e}")
    yield
    logger.info("Company Brain shutting down.")

app = FastAPI(
    title="Company Brain API",
    description="FalkorDB-powered Multi-Agent AI Company Brain with Source-Grounded Evidence",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_no_cache_headers(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

app.include_router(router)

# Mount frontend directory for static serving
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if not FRONTEND_DIR.exists():
    FRONTEND_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=SERVER_HOST, port=SERVER_PORT, reload=True)
