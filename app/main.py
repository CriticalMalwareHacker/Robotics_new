from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from app.routers import router
from app.api.parking_routes import router as parking_router
from app.startup import initialize_app
from shared.config import APP_NAME, APP_VERSION

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(parking_router)
Path("diagram_images").mkdir(exist_ok=True)
Path("generated_labels").mkdir(exist_ok=True)
app.mount("/generated-images", StaticFiles(directory="diagram_images"), name="generated-images")
app.mount("/generated_labels", StaticFiles(directory="generated_labels"), name="generated_labels")
app.mount("/generated-labels", StaticFiles(directory="generated_labels"), name="generated-labels")



@app.on_event("startup")
def startup_event() -> None:
    initialize_app()
