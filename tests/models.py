"""Test models for migration testing."""

from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    """User model for testing."""

    id: int | None = Field(default=None, primary_key=True)
    name: str
    email: str = Field(unique=True)
    is_active: bool = Field(default=True)


class Post(SQLModel, table=True):
    """Post model for testing."""

    id: int | None = Field(default=None, primary_key=True)
    title: str
    content: str
    user_id: int | None = Field(default=None, foreign_key="user.id")
