from app.db.seed import seed_development_data
from app.db.session import SessionLocal

with SessionLocal() as session:
    seed_development_data(session)
