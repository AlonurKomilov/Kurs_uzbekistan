from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tg_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    lang: Mapped[str] = mapped_column(String(16), default="uz_cy", nullable=False)
    subscribed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    digest_schedule: Mapped[str] = mapped_column(
        String(16), default="morning", nullable=False
    )  # morning | evening | twice | custom | off
    digest_time: Mapped[datetime | None] = mapped_column(Time, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Bank(Base):
    __tablename__ = "banks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)

    rates: Mapped[list["BankRate"]] = relationship(back_populates="bank")


class BankRate(Base):
    __tablename__ = "bank_rates"
    __table_args__ = (
        Index("ix_bankrate_bank_code_fetched", "bank_id", "code", "fetched_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bank_id: Mapped[int] = mapped_column(Integer, ForeignKey("banks.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(3), nullable=False)
    buy: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    sell: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    bank: Mapped["Bank"] = relationship(back_populates="rates")


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tg_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(3), nullable=False)
    direction: Mapped[str] = mapped_column(String(5), nullable=False)  # "above" or "below"
    threshold: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    triggered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ChannelSub(Base):
    __tablename__ = "channel_subs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    schedule: Mapped[str] = mapped_column(
        String(16), default="morning", nullable=False
    )  # morning | evening | twice
    lang: Mapped[str] = mapped_column(String(16), default="uz_cy", nullable=False)
    added_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
