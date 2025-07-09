#!/usr/bin/env python3
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import AppController

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create the FastAPI application
app_controller: AppController | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting the pi-stream application")
    global app_controller
    app_controller = AppController()
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

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
