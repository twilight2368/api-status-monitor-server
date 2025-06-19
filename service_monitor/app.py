from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from models import db, Service, StatusService, ServiceStatus, HttpMethod
from sqlalchemy import Enum as PgEnum
from cron_helper import check_service_job, add_cron_job, scheduler
from datetime import datetime
from flask_cors import CORS
import enum
import json
import requests

app = Flask(__name__)
CORS(app)
app.config['SQLALCHEMY_DATABASE_URI'] = (
    'mysql+pymysql://monitor_bkademy:Bkademy%402025'
    '@localhost:3306/monitor_db?charset=utf8mb4'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

@app.route("/")
def index():
    return render_template("index.html")

# API: Lấy danh sách dịch vụ
@app.route("/api/services", methods=["GET"])
def get_services():
    services = Service.query.all()
    result = []
    for s in services:
        result.append({
            "id": s.id,
            "name": s.name,
            "url": s.url,
            "method": s.method.value,
            "data": s.data,
            "cookies": s.cookie,
            "timeout": 5,
            "cron": s.cron
        })
    return jsonify(result)

# API: Thêm dịch vụ
@app.route("/api/services", methods=["POST"])
def add_service():
    data = request.json
    new_service = Service(
        name=data["name"],
        url=data["url"],
        method=HttpMethod[data["method"].upper()],
        data=data.get("data", {}),
        cookie=data.get("cookies", {}),
        cron=data.get("schedule_time")
    )
    db.session.add(new_service)
    db.session.commit()
    return jsonify({"message": "Dịch vụ đã được thêm"}), 201

# API: Cập nhật dịch vụ
@app.route("/api/services/<int:service_id>", methods=["PUT"])
def update_service(service_id):
    service = Service.query.get_or_404(service_id)
    data = request.json
    service.name = data["name"]
    service.url = data["url"]
    service.method = HttpMethod[data["method"].upper()]
    service.data = data.get("data", {})
    service.cookie = data.get("cookies", {})
    service.cron = data.get("schedule_time")
    db.session.commit()
    return jsonify({"message": "Cập nhật thành công"})

# API: Xoá dịch vụ
@app.route("/api/services/<int:service_id>", methods=["DELETE"])
def delete_service(service_id):
    service = Service.query.get_or_404(service_id)
    # Xoá status trước (nếu có)
    status = StatusService.query.filter_by(id_service=service.id).first()
    if status:
        db.session.delete(status)
    db.session.delete(service)
    db.session.commit()
    return jsonify({"message": f"Đã xoá dịch vụ '{service.name}'"})

@app.route("/api/services/<int:service_id>/check", methods=["GET"])
def check_service(service_id):
    service = Service.query.get_or_404(service_id)

    # Gọi logic kiểm tra thực tế và cập nhật DB
    result = check_service_job(service.id, app)

    # Nếu service có cron thì thêm vào scheduler (chạy định kỳ)
    if service.cron:
        add_cron_job(service, app)

    return jsonify(result)

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        scheduler.start()
        # Khởi tạo job cho các service đã có cron
        for service in Service.query.all():
            if service.cron:
                add_cron_job(service, app)
    app.run(debug=True)
