from sqlalchemy import ForeignKey, String, BigInteger
from sqlalchemy.orm import Mapped, DeclarativeBase, mapped_column
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine

from datetime import date, datetime, time
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    create_engine, Column, Integer, String, Boolean, 
    Text, Float, BigInteger, Date, Time, TIMESTAMP,
    ForeignKey, UniqueConstraint, JSON, Text, func
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker, Session
import json

engine = create_async_engine(url='sqlite+aiosqlite:///db.sqlite3', echo=True)

async_session = async_sessionmaker(bind=engine, expire_on_commit=False)


class Base(AsyncAttrs, DeclarativeBase):
    pass

class User(Base):
    """Пользователь"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, index=True)
    tg_id = Column(BigInteger, unique=True, nullable=False, index=True)  # Telegram User ID
    username = Column(String(255))
    first_name = Column(String(255))
    last_name = Column(String(255))
    created_at = Column(TIMESTAMP, server_default=func.now())
    timezone = Column(String(50), default='UTC')
    
    # Связи
    habits = relationship("UserHabit", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(tg_id={self.tg_id}, username={self.username})>"


class HabitTemplate(Base):
    """Шаблон привычки (предопределенные и кастомные)"""
    __tablename__ = 'habit_templates'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    icon = Column(String(100))  # Эмодзи или название иконки
    is_custom = Column(Boolean, default=False)  # False - системный шаблон, True - создан пользователем
    is_active = Column(Boolean, default=True)   # Активен ли для выбора
    default_attributes = Column(JSON, default=[])  # Список доп. атрибутов
    
    # Связи
    user_habits = relationship("UserHabit", back_populates="habit_template", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<HabitTemplate(name={self.name}, is_custom={self.is_custom})>"
    
    def get_default_attributes(self) -> List[Dict[str, Any]]:
        """Получить дефолтные атрибуты как список словарей"""
        if isinstance(self.default_attributes, str):
            return json.loads(self.default_attributes)
        return self.default_attributes or []


class UserHabit(Base):
    """Активация привычки пользователем (связь User-HabitTemplate)"""
    __tablename__ = 'user_habits'
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    habit_template_id = Column(Integer, ForeignKey('habit_templates.id', ondelete='CASCADE'), nullable=False)
    is_active = Column(Boolean, default=True)  # Отслеживает ли сейчас пользователь
    target_value = Column(Float)  # Целевое значение
    target_unit = Column(String(50))  # Единица измерения
    custom_attributes = Column(JSON, default=[])  # Кастомные атрибуты пользователя
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    # Ограничение уникальности
    __table_args__ = (UniqueConstraint('user_id', 'habit_template_id', name='_user_habit_uc'),)
    
    # Связи
    user = relationship("User", back_populates="habits")
    habit_template = relationship("HabitTemplate", back_populates="user_habits")
    reminders = relationship("HabitReminder", back_populates="user_habit", cascade="all, delete-orphan")
    logs = relationship("HabitLog", back_populates="user_habit", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<UserHabit(user_id={self.user_id}, habit_template_id={self.habit_template_id})>"
    
    def get_all_attributes(self) -> List[Dict[str, Any]]:
        """Получить все атрибуты (дефолтные + кастомные)"""
        default = self.habit_template.get_default_attributes() if self.habit_template else []
        custom = self.custom_attributes if self.custom_attributes else []
        
        if isinstance(custom, str):
            custom = json.loads(custom)
            
        # Объединяем, кастомные атрибуты имеют приоритет
        attr_dict = {attr.get('name'): attr for attr in default}
        for attr in custom:
            if isinstance(attr, dict) and 'name' in attr:
                attr_dict[attr['name']] = attr
        
        return list(attr_dict.values())


class HabitReminder(Base):
    """Напоминание для привычки пользователя"""
    __tablename__ = 'habit_reminders'
    
    id = Column(Integer, primary_key=True, index=True)
    user_habit_id = Column(Integer, ForeignKey('user_habits.id', ondelete='CASCADE'), nullable=False)
    reminder_time = Column(Time, nullable=False)  # Время напоминания
    days_of_week = Column(String(7), default='1111111')  # 0-выкл, 1-вкл, Пн-Вс
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    # Связи
    user_habit = relationship("UserHabit", back_populates="reminders")
    
    def __repr__(self):
        return f"<HabitReminder(time={self.reminder_time}, days={self.days_of_week})>"
    
    def is_active_for_day(self, weekday: int) -> bool:
        """
        Проверяет, активно ли напоминание для дня недели
        weekday: 0 - понедельник, 6 - воскресенье
        """
        if len(self.days_of_week) != 7:
            return False
        return self.days_of_week[weekday] == '1'


class HabitLog(Base):
    """Лог выполнения привычки (дневные записи)"""
    __tablename__ = 'habit_logs'
    
    id = Column(Integer, primary_key=True, index=True)
    user_habit_id = Column(Integer, ForeignKey('user_habits.id', ondelete='CASCADE'), nullable=False)
    logged_date = Column(Date, nullable=False, default=func.current_date())
    is_completed = Column(Boolean, default=False)  # Выполнена ли привычка
    quantity = Column(Float)  # Количество (литры, минуты и т.д.)
    note = Column(Text)  # Текстовая заметка
    attributes = Column(JSON, default={})  # Дополнительные атрибуты
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    
    # Ограничение уникальности - одна запись в день на привычку
    __table_args__ = (UniqueConstraint('user_habit_id', 'logged_date', name='_habit_log_uc'),)
    
    # Связи
    user_habit = relationship("UserHabit", back_populates="logs")
    
    def __repr__(self):
        return f"<HabitLog(date={self.logged_date}, completed={self.is_completed})>"
    
    def get_attributes_dict(self) -> Dict[str, Any]:
        """Получить атрибуты как словарь"""
        if isinstance(self.attributes, str):
            return json.loads(self.attributes)
        return self.attributes or {}

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)