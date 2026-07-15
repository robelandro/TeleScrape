import logging
import bcrypt
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models import User, TargetChannel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def seed_db(db: Session):
    # Create admin user
    admin_user = db.query(User).filter_by(username="admin").first()
    if not admin_user:
        admin_user = User(
            username="admin",
            password_hash=get_password_hash("admin123"),
            role="admin"
        )
        db.add(admin_user)
        logger.info("Admin user created.")
    else:
        logger.info("Admin user already exists.")

    # Create viewer user
    viewer_user = db.query(User).filter_by(username="viewer").first()
    if not viewer_user:
        viewer_user = User(
            username="viewer",
            password_hash=get_password_hash("viewer123"),
            role="viewer"
        )
        db.add(viewer_user)
        logger.info("Viewer user created.")
    else:
        logger.info("Viewer user already exists.")

    db.commit()
    db.refresh(admin_user)

    # Seed some target channels
    channels = ["@react_gigs", "@python_gigs", "@data_gigs"]
    for ch in channels:
        existing = db.query(TargetChannel).filter_by(channel_name=ch).first()
        if not existing:
            channel = TargetChannel(
                channel_name=ch,
                is_active=True,
                added_by=admin_user.id
            )
            db.add(channel)
            logger.info(f"Channel {ch} seeded.")
        else:
            logger.info(f"Channel {ch} already exists.")

    db.commit()

if __name__ == "__main__":
    db = SessionLocal()
    try:
        seed_db(db)
    finally:
        db.close()
