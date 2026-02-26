

from sqlalchemy.orm import Session
from app.db.models import OAuthState


class OAuthStateRepository:

    def __init__(self, db: Session):
        self.db = db

    def get_by_state(self, state: str) -> OAuthState | None:
        return (
            self.db.query(OAuthState)
            .filter(OAuthState.state == state)
            .first()
        )

    def create(self, state: str) -> OAuthState:
        obj = OAuthState(state=state)
        self.db.add(obj)
        self.db.flush()
        return obj

    def delete(self, obj: OAuthState):
        self.db.delete(obj)

    def save(self):
        self.db.commit()