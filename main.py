#!/usr/bin/env python3
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import get_app_controller

app_controller = get_app_controller()

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting the pi-stream application")
    from api import router as api_router

    app.include_router(api_router)
    yield
    logger.info("Cleaning up resources")
    if app_controller:
        # Ensure the AppController is cleaned up properly
        app_controller.cleanup()


app = FastAPI(
    lifespan=lifespan,
    title="Pi Stream",
    version="1.0.0",
    description="A music streaming application for Raspberry Pi",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for CORS
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)


# register all @app routes in api.py
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
