from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
from flask import current_app
from datetime import datetime
import requests
import os
from models import db, Service, StatusService, ServiceStatus, HttpMethod, CategoryService

scheduler = BackgroundScheduler()
DISCORD_WEBHOOK_URL = f"{os.getenv('DISCORD_WEBHOOK')}"


def send_discord_alert(service_name, service_url, error_msg):
    content = f"❗ Dịch vụ **{service_name}** đang **DOWN**.\n🔗 URL: {service_url}\n📛 Lỗi: `{error_msg}`"
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": content})
    except Exception as ex:
        print(f"[ERROR] Gửi Discord thất bại: {ex}")


def check_service_job(service_id, app):
    with app.app_context():
        service = Service.query.get(service_id)
        category_obj = CategoryService.query.filter_by(id_service=service_id).first()
        category = category_obj.category if category_obj else None
        if not service:
            return None

        try:
            # Set timezone to UTC+7
            tz = pytz.timezone('Asia/Bangkok')
            start = datetime.now(tz)

            method = service.method
            request_kwargs = {
                "url": service.url,
                "cookies": service.cookie or {},
                "timeout": service.timeout or 5
            }

            if method == HttpMethod.POST:
                request_kwargs["json"] = service.data or {}
                response = requests.post(**request_kwargs)
            elif method == HttpMethod.PUT:
                request_kwargs["json"] = service.data or {}
                response = requests.put(**request_kwargs)
            elif method == HttpMethod.PATCH:
                request_kwargs["json"] = service.data or {}
                response = requests.patch(**request_kwargs)
            elif method == HttpMethod.DELETE:
                response = requests.delete(**request_kwargs)
            else:  # Default to GET
                response = requests.get(**request_kwargs)

            # Determine service status
            if 400 <= response.status_code < 600:
                status = ServiceStatus.DOWN
                send_discord_alert(
                    service.name, service.url, f"HTTP {response.status_code} - {response.text}")
            else:
                status = ServiceStatus.UP

            finish_time = datetime.now(tz)

            # Log status to DB
            status_entry = StatusService(
                id_service=service.id,
                name=service.name,
                status=status,
                finish_time=finish_time
            )
            db.session.add(status_entry)
            db.session.commit()

            return {
                "name": service.name,
                "status": status.value,
                "status_code": response.status_code,
                "category": category,
                "response_time": round((finish_time - start).total_seconds() * 1000),
                "error": None if status == ServiceStatus.UP else f"HTTP {response.status_code}"
            }

        except Exception as e:
            finish_time = datetime.now(tz)

            status_entry = StatusService(
                id_service=service.id,
                name=service.name,
                status=ServiceStatus.DOWN,
                finish_time=finish_time
            )
            db.session.add(status_entry)
            db.session.commit()

            send_discord_alert(service.name, service.url, str(e))
            return {
                "name": service.name,
                "status": "DOWN",
                "category": category,
                "error": str(e)
            }


def add_cron_job(service, app):
    if not service.cron:
        return

    job_id = f"service_{service.id}:{service.name}:{service.method.value}:{service.url}"
    if scheduler.get_job(job_id):
        print(f"REMOVE {job_id}")
        scheduler.remove_job(job_id)

    cron_parts = service.cron.strip().split()
    if len(cron_parts) == 5:
        cron_full = service.cron.strip()
    elif len(cron_parts) < 5:
        cron_full = " ".join(cron_parts + ["*"] * (5 - len(cron_parts)))
    else:
        raise ValueError(
            f"Invalid cron format '{service.cron}' (must have 5 fields)")

    try:
        trigger = CronTrigger.from_crontab(cron_full)
        scheduler.add_job(
            func=check_service_job,
            trigger=trigger,
            args=[service.id, app],
            id=job_id,
            replace_existing=True
        )
        print(f"Add job successful {job_id}")
    except Exception as e:
        print(f"[ERROR] Failed to add cron for service ID {service.id}: {e}")
