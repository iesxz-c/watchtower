from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import logging
import os

from watchtower.core.database import engine, Base, SessionLocal
from watchtower.core.models import MonitorTarget
from watchtower.core.config import get_yaml_config
from watchtower.api import ingest, health, dashboard, status, admin
from watchtower.workers.endpoint_worker import run_endpoint_checks
from watchtower.workers.log_parser import run_log_parser_scan

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

Base.metadata.create_all(bind=engine)

def seed_targets_from_yaml():
    db = SessionLocal()
    try:
        yaml_config = get_yaml_config()
        for t_conf in yaml_config.monitoring.targets:
            existing = db.query(MonitorTarget).filter(MonitorTarget.name == t_conf.name).first()
            if not existing:
                target = MonitorTarget(
                    name=t_conf.name,
                    url=t_conf.url,
                    method=t_conf.method,
                    expected_status=t_conf.expected_status,
                    timeout_s=t_conf.timeout_s,
                    interval_s=t_conf.interval_s,
                    enabled=t_conf.enabled,
                    headers_json=t_conf.headers
                )
                db.add(target)
        db.commit()
    except Exception as e:
        logger.error(f"Error seeding targets: {e}")
    finally:
        db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    seed_targets_from_yaml()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_endpoint_checks, 'interval', seconds=60, id='endpoint_checks')
    scheduler.add_job(run_log_parser_scan, 'interval', minutes=5, id='log_parser')
    
    scheduler.start()
    logger.info("Scheduler started.")
    
    yield
    
    scheduler.shutdown()
    logger.info("Scheduler stopped.")

app = FastAPI(title="WatchTower API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(ingest.router)
app.include_router(dashboard.router)
app.include_router(status.router)
app.include_router(admin.router)

sdk_dir = os.path.join(os.path.dirname(__file__), '..', 'sdk')
if not os.path.exists(sdk_dir):
    os.makedirs(sdk_dir)
app.mount("/sdk", StaticFiles(directory=sdk_dir), name="sdk")
