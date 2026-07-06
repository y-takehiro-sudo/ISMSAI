from sqlalchemy.orm import sessionmaker
from app.db.models import get_engine

_engine = None
_SessionLocal = None


def get_session_factory(db_path: str = "isms.db"):
    global _engine, _SessionLocal
    if _SessionLocal is None:
        _engine = get_engine(db_path)
        _SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
    return _SessionLocal


def get_db():
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
