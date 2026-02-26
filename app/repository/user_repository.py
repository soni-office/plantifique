
from sqlalchemy.orm import Session
from app.db.models import User


class UserRepository:

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: int) -> User | None:
        return self.db.query(User).filter(User.id == user_id).first()

    def get_by_tiktok_open_id(self, open_id: str) -> User | None:
        return (
            self.db.query(User)
            .filter(User.tiktok_open_id == open_id)
            .first()
        )

    def create(self, open_id: str, username: str | None = None) -> User:
        user = User(
            tiktok_open_id=open_id,
            username=username,
        )
        self.db.add(user)
        self.db.flush()
        return user

    def save(self):
        self.db.commit()