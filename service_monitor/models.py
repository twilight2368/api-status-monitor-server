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


