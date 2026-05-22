from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.config.settings import settings

engine = create_engine(settings.db_url, pool_pre_ping=True, pool_size=5)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
