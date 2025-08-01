from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Enum as PgEnum
import enum

# Khởi tạo đối tượng SQLAlchemy
db = SQLAlchemy()

# ENUM cho phương thức HTTP


class HttpMethod(enum.Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"

# ENUM cho trạng thái dịch vụ


class ServiceStatus(enum.Enum):
    UP = "UP"
    DOWN = "DOWN"

# Bảng Service


class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    url = db.Column(db.Text, nullable=False)
    method = db.Column(PgEnum(HttpMethod), nullable=False)
    data = db.Column(db.JSON, nullable=True)
    cookie = db.Column(db.JSON, nullable=True)
    cron = db.Column(db.String(20), nullable=True)
    timeout = db.Column(db.Integer, default=5)
    category_id = db.Column(db.Integer, db.ForeignKey(
        'category.id', ondelete='SET NULL'), nullable=True)
    # Quan hệ đến StatusService
    statuses = db.relationship(
        'StatusService',
        backref='service',
        cascade='all, delete-orphan',
        passive_deletes=True  # Cho phép ON DELETE CASCADE hoạt động
    )

# Bảng StatusService (lưu kết quả kiểm tra)


class StatusService(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    id_service = db.Column(
        db.Integer,
        db.ForeignKey('service.id', ondelete='CASCADE'),
        nullable=False
    )
    name = db.Column(db.String(255), nullable=False)
    status = db.Column(PgEnum(ServiceStatus), nullable=False)
    finish_time = db.Column(db.DateTime, nullable=False)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(255), nullable=False, unique=True)
    password_hash = db.Column(db.String(512), nullable=False)

# Bảng Category (mỗi category có nhiều service)


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    # Quan hệ 1-n với Service
    services = db.relationship(
        'Service', backref='category', cascade="all, delete", passive_deletes=True)


class APIKey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    key = db.Column(db.String(2000))
    create_time = db.Column(db.DateTime, nullable=False)
