from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import init_db
from app.api.v1.routers import servers

app = FastAPI(title="Enviroments API", version="1.0.0", description="Server & switch management")

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup
@app.on_event("startup")
def on_startup():
    init_db()

# Include routers
app.include_router(servers.router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "ok"}
