import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Boolean, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

class Click(db.Model): 
    """
    Represents an access log (click) for a shortened URL.
    
    Stores analytics data like device information, geographic location, 
    and request origin. Uses an IP hash to determine unique clicks while 
    maintaining user privacy and complying with data protection regulations.
    """
    __tablename__ = "clicks"
    __table_args__ = (
            db.Index("ix_clicks_url_time", "url_id", "clicked_at"),
            db.Index("ix_clicks_url_country", "url_id", "country"),
        )
    id: Mapped[int] = mapped_column(primary_key=True)
    url_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        db.ForeignKey("short_urls.id", ondelete="CASCADE"), index=True
        )
        
    ip_hash: Mapped[str] = mapped_column(String(64), index=True)
    is_unique: Mapped[bool] = mapped_column(Boolean, default=True)

    # Analytcs fields are nullable because clients or privacy tools might not provide headers like referer or user_agent
    referer: Mapped[str] = mapped_column(String(500), nullable=True)
    user_agent_raw: Mapped[str] = mapped_column(String(500), nullable=True)
    browser: Mapped[str] = mapped_column(String(50), nullable=True)
    os: Mapped[str] = mapped_column(String(50), nullable=True)
    device_type: Mapped[str] = mapped_column(String(50), nullable=True)
    
    # Geo fields are nullable because IṔ resolution might fail 
    country: Mapped[str] = mapped_column(String(100), nullable=True)
    region: Mapped[str] = mapped_column(String(100), nullable=True)
    city: Mapped[str] = mapped_column(String(100), nullable=True)
    
    clicked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, default=lambda: datetime.now(timezone.utc))
    url: Mapped["ShortURL"] = relationship(back_populates="clicks")

