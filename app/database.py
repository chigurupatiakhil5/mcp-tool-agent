from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

# pool_size: how many connections to keep open and ready at all times.
# max_overflow: how many *extra* connections we're allowed to open temporarily
#   if all pool_size connections are busy, before requests start queuing.
# pool_pre_ping: test a connection with a cheap query before handing it to a
#   request, so a connection that died quietly (e.g. DB restarted) gets
#   replaced instead of causing a confusing runtime error.
engine = create_engine(
    settings.database_url,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency: hands an endpoint one database session borrowed
    from the pool, and guarantees it's returned to the pool (via close())
    even if the endpoint raises an exception."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
