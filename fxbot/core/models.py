from sqlalchemy import Column, Integer, String, BigInteger, DateTime, ForeignKey, Numeric, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from infrastructure.db import Base


class User(Base):
    """User model for storing Telegram user information."""
    
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    tg_user_id = Column(BigInteger, unique=True, nullable=False, index=True)
    lang = Column(String(16), default="uz_cy", nullable=False)
    tz = Column(String(32), default="Asia/Tashkent", nullable=False)
    subscribed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<User(id={self.id}, tg_user_id={self.tg_user_id}, lang={self.lang}, subscribed={self.subscribed})>"


class Bank(Base):
    """Bank model for storing bank information."""
    
    __tablename__ = "banks"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    region = Column(String(100), nullable=True)
    website = Column(String(500), nullable=True)
    
    # Relationship to bank rates
    rates = relationship("BankRate", back_populates="bank")
    
    def __repr__(self):
        return f"<Bank(id={self.id}, name={self.name}, slug={self.slug})>"


class BankRate(Base):
    """Bank rate model for storing currency exchange rates."""
    
    __tablename__ = "bank_rates"
    
    id = Column(Integer, primary_key=True, index=True)
    bank_id = Column(Integer, ForeignKey("banks.id"), nullable=False, index=True)
    code = Column(String(3), nullable=False, index=True)  # USD, EUR, RUB etc.
    buy = Column(Numeric(10, 4), nullable=False)  # Buy rate
    sell = Column(Numeric(10, 4), nullable=False)  # Sell rate  
    fetched_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    # Relationship to bank
    bank = relationship("Bank", back_populates="rates")
    
    def __repr__(self):
        return f"<BankRate(id={self.id}, bank_id={self.bank_id}, code={self.code}, sell={self.sell})>"