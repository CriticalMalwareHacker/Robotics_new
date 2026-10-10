from infrastructure.database import init_db
from shared.logging_config import get_logger
from backend.services.parking.monitor import start as start_parking_monitor

logger = get_logger("startup")


def initialize_app() -> None:
    init_db()
    # Vision monitoring is independent of robot motion mode. Start it on boot
    # so the HUD has live OpenCV results while the robot is parked or manual.
    start_parking_monitor()
    logger.info("PrintSensei startup complete")
