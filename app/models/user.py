import secrets
import uuid
from flask import url_for
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db


class User(db.Model):
    """Represents a registered user in the application.

    Attributes:
        id (uuid.UUID): Primary key, auto-generated UUID.
        email (str): User's unique email address.
        password_hash (str): Hashed password for authentication.
        api_key (str): Unique token for API access.
        is_active (bool): Flag indicating if the user account is active.
        created_at (datetime): Timestamp of account creation.
        updated_at (datetime): Timestamp of the last account update.
        urls (list[ShortURL]): Dynamic relationship to the URLs owned by the user.
    """
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
        """Hashes the provided password and stores it.

        Args:
            password (str): The plain-text password to hash.
        """
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verifies if the provided password matches the stored hash.

        Args:
            password (str): The plain-text password to verify.

        Returns:
            bool: True if the password matches, False otherwise.
        """
        return check_password_hash(self.password_hash, password)

    def rotate_api_key(self) -> str:
        """Generates and sets a new secure API key for the user.

        Returns:
            str: The newly generated API key.
        """
        self.api_key = secrets.token_urlsafe(32)
        return self.api_key
    def to_dict(self) -> dict:
        """Serializes the user object into a dictionary.

        Returns:
            dict: The user's public profile data and hypermedia links.
        """
        return {
        "id": str(self.id),
        "email": self.email,
        "created_at": self.created_at.isoformat(),
        "links": {
            "self": url_for("auth.me", _external=True),
            "urls": url_for("urls.list_urls", _external=True),
            },
        }
    def __repr__(self) -> str:
        """Returns a string representation of the User object."""
        return f"<User {self.email}>"