#!/usr/bin/env python3
import logging
import threading

from app import AppController

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app_controller: AppController | None = None


def main():
    logger.info("Starting the pi-stream application")
    # Your main application logic here
    global app_controller
    app_controller = AppController()
    # Wait until all application threads have terminated (for this example,
    # this is when all deck handles are closed).
    for t in threading.enumerate():
        try:
            t.join()
        except RuntimeError:
            pass
    logger.info("Pi-stream application finished successfully")
    return 0


if __name__ == "__main__":
    try:
        exit_code = main()
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        exit_code = 1
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, exiting gracefully")
        exit_code = 0
    finally:
        if app_controller:
            app_controller.cleanup()
        logger.info("Exiting the pi-stream application")
    exit(exit_code)
