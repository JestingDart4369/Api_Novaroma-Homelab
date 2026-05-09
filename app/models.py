from typing import Optional
from datetime import datetime
from sqlalchemy import String, Boolean, Integer, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20), default="user")  # "user", "admin", "superAdmin", "Root"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ApiConfig(Base):
    __tablename__ = "api_config"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    api_name: Mapped[str] = mapped_column(String(50), unique=True, index=True)  # e.g. "nasa", "openweather"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    max_calls_per_hour: Mapped[int] = mapped_column(Integer, default=1000)


class RoleLimits(Base):
    __tablename__ = "role_limits"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    role_name: Mapped[str] = mapped_column(String(20), unique=True, index=True)  # "user", "admin", "superAdmin", "Root"
    max_calls_per_hour: Mapped[int] = mapped_column(Integer, default=1000)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Software(Base):
    __tablename__ = "software"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    health: Mapped[str] = mapped_column(String(20), default="unknown")  # "ok", "warning", "error", "unknown"
    last_heartbeat: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)      # device-side signal (device blocks itself)
    server_enabled: Mapped[bool] = mapped_column(Boolean, default=True) # server-side blocking (API returns 503)


class Hardware(Base):
    __tablename__ = "hardware"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    health: Mapped[str] = mapped_column(String(20), default="unknown")  # "ok", "warning", "error", "unknown"
    last_heartbeat: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)   # free-form device config
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # runtime health details
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)        # device-side signal (device blocks itself)
    server_enabled: Mapped[bool] = mapped_column(Boolean, default=True)   # server-side blocking (API returns 503)
