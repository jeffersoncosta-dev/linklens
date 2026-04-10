import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db

class ShortURL(db.Model):
    """
    Represents a shortened URL entity in the database.

    Manages original URL maping, access limits (time and click-based), amd relashionships 
    with the URL owner and click analitics 
    """

    __tablename__ = "short_urls"
    __table_args__ = (
        db.Index("ix_short_urls_user_active", "user_id", "is_active"),
    )
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(
        String(64), unique=True, index=True)
    original_url: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String(255), nullable=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        db.ForeignKey("users.id"),
        ondelete="CASCADE",
        index=True
        )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    max_clicks: Mapped[int] = mapped_column(Integer, nullable=True)
    click_count: Mapped[int] = mapped_column(Integer, default=0, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        )
    owner: Mapped["User"] = relationship(back_populates="urls")
    clicks: Mapped[list["Click"]] = relationship(back_populates="url", cascade="all, delete-orphan")
    
    @property
    def is_expired(self) -> bool:
        """
        Dynamically checks if the URL passed the expiration date.

        Returns False if no expiration date is set (if URL has inifinite lifespan)
        """
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def is_click_limit_reached(self) -> bool:
        """
        Check if the URL has reached its maximum amount of clicks

        Returns False if max_clicks is None (if unlimited clicks is allowed)
        """
        if self.max_clicks is None:
            return False
        return self.click_count >= self.max_clicks

    @property
    def is_accessible(self) -> bool:
        return self.is_active and not self.is_expired and not self.is_click_limit_reached

    def to_dict(self, base_url: str = "") -> dict:
        """
        Serializes the ShortURL instance into a dictionary for JSON responses.

        Args:
        base_url (str): The base aplication URL to contruct the full short_url.
        Returns:
            dict: The serialized URL data including HATEOAS links. 
        """
        return {
            "id": str(self.id),
            "slug": self.slug,
            "original_url": self.original_url,
            "short_url": f"{base_url.rstrip('/')}/{self.slug}",
            "title": self.title,
            "is_active": self.is_active,
            "click_count": self.click_count,
            "max_clicks": self.max_clicks,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat(),
            "is_expired": self.is_expired,
            "links": {
                "self": f"/api/v1/urls/{self.slug}",
                "analytics": f"/api/v1/urls/{self.slug}/analytics",
                "qr": f"/api/v1/urls/{self.slug}/qr"
            }
        }

    def __repr__(self) -> str:
        return f"<ShortURL {self.slug}>"
        