

from sqlalchemy.orm import Session
from app.db.models import TikTokToken


class TikTokTokenRepository:

    def __init__(self, db: Session):
        self.db = db

    def get_by_user_id(self, user_id: int) -> TikTokToken | None:
        return (
            self.db.query(TikTokToken)
            .filter(TikTokToken.user_id == user_id)
            .first()
        )

    def create(self, user_id: int) -> TikTokToken:
        token = TikTokToken(user_id=user_id)
        self.db.add(token)
        self.db.flush()
        return token

    def save(self):
        self.db.commit()