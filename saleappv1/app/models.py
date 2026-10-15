from datetime import datetime
from app import db
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship


class Category(db.Model):
    __tablename__ = "category"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    products = relationship("Product", backref="category", lazy=True)

    def __str__(self):
        return self.name


class Product(db.Model):
    __tablename__ = "product"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    description = Column(String(255))
    price = Column(Float, default=0)
    image = Column(String(255))
    active = Column(Boolean, default=True)
    created_date = Column(DateTime, default=datetime.now)
    category_id = Column(Integer, ForeignKey(Category.id), nullable=False)

    def __str__(self):
        return self.name


class User(db.Model):
    __tablename__ = "user"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    username = Column(String(50), unique=True, nullable=False)
    password = Column(String(100), nullable=False)  # lưu mã băm MD5 theo yêu cầu 5
    avatar = Column(String(255))
    active = Column(Boolean, default=True)
    joined_date = Column(DateTime, default=datetime.now)
    user_role = Column(
        String(20), default="user"
    )  # 'admin' hoặc 'user' dùng cho phân quyền admin (YC4)

    def __str__(self):
        return self.username
