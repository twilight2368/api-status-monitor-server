from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Enum as PgEnum
from datetime import datetime
import enum
import json
import requests

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:@localhost/test?charset=utf8mb4'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ENUM cho phương thức HTTP
class HttpMethod(enum.Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"

# ENUM cho status dịch vụ
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

# Bảng StatusService (lưu kết quả kiểm tra)
class StatusService(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    id_service = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False, unique=True)
    name = db.Column(db.String(255), nullable=False)
    status = db.Column(PgEnum(ServiceStatus), nullable=False)
    finish_time = db.Column(db.DateTime, nullable=False)

    service = db.relationship('Service', backref=db.backref('statuses', lazy=True))

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
            "schedule_time": None,
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
    db.session.delete(service)
    db.session.commit()
    return jsonify({"message": f"Đã xoá dịch vụ '{service.name}'"})

# API: Kiểm tra dịch vụ và lưu trạng thái
@app.route("/api/services/<int:service_id>/check", methods=["GET"])
def check_service(service_id):
    service = Service.query.get_or_404(service_id)
    try:
        start = datetime.now()
        if service.method == HttpMethod.POST:
            response = requests.post(
                service.url,
                json=service.data or {},
                cookies=service.cookie or {},
                timeout=5
            )
        else:
            response = requests.get(
                service.url,
                cookies=service.cookie or {},
                timeout=5
            )

        status = ServiceStatus.UP if response.status_code == 200 else ServiceStatus.DOWN
        finish_time = datetime.now()

        # Cập nhật hoặc tạo mới trạng thái kiểm tra
        status_entry = StatusService.query.filter_by(id_service=service.id).first()
        if status_entry:
            status_entry.status = status
            status_entry.finish_time = finish_time
        else:
            status_entry = StatusService(
                id_service=service.id,
                name=service.name,
                status=status,
                finish_time=finish_time
            )
            db.session.add(status_entry)

        db.session.commit()

        return jsonify({
            "status": status.value,
            "status_code": response.status_code,
            "response_time": (finish_time - start).total_seconds() * 1000,
            "error": None if status == ServiceStatus.UP else f"HTTP {response.status_code}"
        })
    except Exception as e:
        finish_time = datetime.now()
        status_entry = StatusService.query.filter_by(id_service=service.id).first()
        if status_entry:
            status_entry.status = ServiceStatus.DOWN
            status_entry.finish_time = finish_time
        else:
            status_entry = StatusService(
                id_service=service.id,
                name=service.name,
                status=ServiceStatus.DOWN,
                finish_time=finish_time
            )
            db.session.add(status_entry)

        db.session.commit()

        return jsonify({
            "status": "DOWN",
            "error": str(e)
        })

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
