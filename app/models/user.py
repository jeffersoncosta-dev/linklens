import secrets
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db


class User(db.Model):
    __tablename__ = 'users'
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
        )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True)

    password_hash: Mapped[str] = mapped_column(
        String(255), nullable=False
        )
    api_key: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        default=lambda: secrets.token_urlsafe(32),
        )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        )
    # Relationship — "ShortURL"  string because class in not yet defined 
    urls: Mapped[list["ShortURL"]] = relationship(
        "ShortURL",
        back_populates="owner",
        lazy="dynamic",
        cascade="all, delete-orphan",
        )
    #methods

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def rotate_api_key(self) -> str:
        self.api_key = secrets.token_urlsafe(32)
        return self.api_key
    def to_dict(self) -> dict:
        return{
            "id": str(self.id),
            "email": self.email,
            "created_at": self.created_at.isoformat(),
            "links": {
                "self": "/api/v1/auth/me",
                "urls": "/api/v1/urls",
            },
        }
    def __repr__(self) -> str:
        return f"<User {self.email}>"