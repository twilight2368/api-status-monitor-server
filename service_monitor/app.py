from functools import wraps
from dotenv import load_dotenv
import os
from flask import Flask, request, jsonify,  send_from_directory, session
from models import db, Service, StatusService,  HttpMethod, User
from sqlalchemy import text
from cron_helper import check_service_job, add_cron_job, scheduler
from flask_cors import CORS
import time
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(BASE_DIR, "dist")

app = Flask(__name__, static_folder=DIST_DIR, static_url_path='')
CORS(app, supports_credentials=True, origins=[
     os.getenv("APP_ORIGIN", "http://localhost:3000")])

load_dotenv()

SQLALCHEMY_DATABASE_URI = (
    f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}/{os.getenv('DB_NAME')}?charset=utf8mb4"
)
APP_ENV = os.getenv("APP_ENV", "development")
app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.getenv("SECRET_KEY", "super-secret-key")
app.config['SESSION_COOKIE_SECURE'] = (APP_ENV == "production")

db.init_app(app)

# TODO: Check login user


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Not logged in'}), 401
        return f(*args, **kwargs)
    return decorated_function


@app.route("/")
def serve_index():
    return send_from_directory(app.static_folder, "index.html")

# Serve the main index.html for the root path


@app.route("/<path:path>")
def static_proxy(path):
    file_path = os.path.join(app.static_folder, path)
    if os.path.exists(file_path):
        return send_from_directory(app.static_folder, path)
    # fallback to index.html for client-side routing
    return send_from_directory(app.static_folder, "index.html")

# TODO: auth route


@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()

    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'error': 'Missing username or password'}), 400

    user = User.query.filter_by(username=data['username']).first()

    if user and check_password_hash(user.password_hash, data['password']):
        session['user_id'] = user.id
        return jsonify({'message': 'Login successful', 'user_id': user.id}), 200
    else:
        return jsonify({'error': 'Invalid credentials'}), 401


@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    return jsonify({'message': 'Logged out successfully'}), 200


@app.route('/api/profile')
@login_required
def get_me():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Not logged in'}), 401

    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    return jsonify({'username': user.username, "message": "User logged in", "login": True})

# API: Lấy danh sách dịch vụ


@app.route("/api/services", methods=["GET"])
@login_required
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
            "timeout": s.timeout,
            "cron": s.cron
        })
    return jsonify(result)

# API: Thêm dịch vụ


@app.route("/api/services", methods=["POST"])
@login_required
def add_service():
    data = request.json
    new_service = Service(
        name=data["name"],
        url=data["url"],
        method=HttpMethod[data["method"].upper()],
        data=data.get("data", {}),
        cookie=data.get("cookies", {}),
        timeout=data.get("timeout", 5),
        cron=data.get("schedule_time")
    )
    db.session.add(new_service)
    db.session.commit()
    # Gọi luôn cronjob sau khi thêm nếu có cron
    if new_service.cron:
        add_cron_job(new_service, app)

    check_service_job(new_service.id, app=app)

    return jsonify({"message": "Dịch vụ đã được thêm"}), 201

# API: Cập nhật dịch vụ


@app.route("/api/services/<int:service_id>", methods=["PUT"])
@login_required
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

    # Xoá cronjob cũ nếu tồn tại
    job_id = f"service_{service.id}"
    existing_job = scheduler.get_job(job_id)
    if existing_job:
        scheduler.remove_job(job_id)

    # Thêm lại cronjob mới nếu có cron
    if service.cron:
        add_cron_job(service, app)

    return jsonify({"message": "Cập nhật thành công"})

# API: Xoá dịch vụ


@app.route("/api/services/<int:service_id>", methods=["DELETE"])
@login_required
def delete_service(service_id):
    service = Service.query.get_or_404(service_id)

    job_id = f"service_{service.id}"
    existing_job = scheduler.get_job(job_id)
    if existing_job:
        scheduler.remove_job(job_id)

    # Xoá status trước (nếu có)
    status = StatusService.query.filter_by(id_service=service.id).first()
    if status:
        db.session.delete(status)

    db.session.delete(service)
    db.session.commit()

    return jsonify({"message": f"Đã xoá dịch vụ '{service.name}'"})


@app.route("/api/services/<int:service_id>/check", methods=["GET"])
@login_required
def check_service(service_id):
    service = Service.query.get_or_404(service_id)

    # Gọi logic kiểm tra thực tế và cập nhật DB
    result = check_service_job(service.id, app)

    # # Nếu service có cron thì thêm vào scheduler (chạy định kỳ)
    # if service.cron:
    #     add_cron_job(service, app)

    return jsonify(result)

# API: Lấy status hiện tại của dịch vụ


@app.route("/api/services/<int:service_id>/status", methods=["GET"])
@login_required
def get_service_status(service_id):
    status = StatusService.query.filter_by(id_service=service_id).first()
    if not status:
        return jsonify({"message": "Không có dữ liệu status"}), 404

    return jsonify({
        "id_service": status.id_service,
        "name": status.name,
        "status": status.status.value,
        "finish_time": status.finish_time.strftime("%Y-%m-%d %H:%M:%S")
    })


@app.route("/api/services/<int:service_id>/statuses", methods=["GET"])
@login_required
def get_service_statuses(service_id):
    statuses = (
        StatusService.query
        .filter_by(id_service=service_id)
        .order_by(StatusService.finish_time.desc())  # Get latest first
        .limit(50)
        .all()
    )

    if not statuses:
        return jsonify({"message": "Không có dữ liệu status"}), 404

    # Reverse to make finish_time ascending (oldest → newest)
    statuses = list(reversed(statuses))

    return jsonify([
        {
            "id": status.id,
            "id_service": status.id_service,
            "name": status.name,
            "status": status.status.value,
            "finish_time": status.finish_time.strftime("%Y-%m-%d %H:%M:%S")
        } for status in statuses
    ])


# TODO :Check for db


def wait_for_db():
    """Wait for database to be ready"""
    max_retries = 30
    for i in range(max_retries):
        print("Checking db ready ....")
        try:
            db.session.execute(text('SELECT 1'))
            print("Database connected successfully!")
            return True
        except Exception as e:
            print(f"Database not ready (attempt {i+1}/{max_retries}): {e}")
            time.sleep(2)
    return False

# TODO: Create 1 user only


def create_user(username="admin", password="password"):
    with app.app_context():
        # Delete all existing users
        User.query.delete()
        db.session.commit()

        # Insert new user
        password_hash = generate_password_hash(password)
        user = User(username=username, password_hash=password_hash)

        db.session.add(user)
        db.session.commit()
        print(f"User '{username}' created successfully.")


def init_app():
    with app.app_context():
        if wait_for_db():
            print("Creating tables...")
            db.create_all()
            print("Tables created.")

            scheduler.start()

            create_user(
                username=os.getenv("MONITOR_APP_USER", "admin"),
                password=os.getenv("MONITOR_APP_USER_PASSWORD", "password")
            )

            for service in Service.query.all():
                if service.cron:
                    add_cron_job(service, app)

            return True
        else:
            print("Failed to connect to database after 30 attempts")
            return False


if __name__ == "__main__":
    if init_app():
        app.run(
            host=os.getenv("FLASK_RUN_HOST", "localhost"),
            port=int(os.getenv("FLASK_RUN_PORT", 5000)),
            debug=True
        )
