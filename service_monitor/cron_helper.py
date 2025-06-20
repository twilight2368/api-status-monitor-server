from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from flask import current_app
from datetime import datetime
import requests
from models import db, Service, StatusService, ServiceStatus, HttpMethod

scheduler = BackgroundScheduler()
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1383989758090416231/RFc50m6BwVVaqCz9pHRmLNBVG8lTJja0rkXsKuCr0IYANjRSQ-kHIKuqpDzjnx8K0ZUz"

def send_discord_alert(service_name, service_url, error_msg):
    content = f"❗ Dịch vụ **{service_name}** đang **DOWN**.\n🔗 URL: {service_url}\n📛 Lỗi: `{error_msg}`"
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": content})
    except Exception as ex:
        print(f"[ERROR] Gửi Discord thất bại: {ex}")
        
def check_service_job(service_id, app):
    with app.app_context():
        service = Service.query.get(service_id)
        if not service:
            return None

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

            if 400 <= response.status_code < 600:
                status = ServiceStatus.DOWN
            else:
                status = ServiceStatus.UP
            finish_time = datetime.now()

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

            return {
                "name": service.name,
                "status": status.value,
                "status_code": response.status_code,
                "response_time": round((finish_time - start).total_seconds() * 1000),
                "error": None if status == ServiceStatus.UP else f"HTTP {response.status_code}"
            }
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
            send_discord_alert(service.name, service.url, str(e))
            return {
                "name": service.name,
                "status": "DOWN",
                "error": str(e)
            }

def add_cron_job(service, app):  
    if not service.cron:
        return

    job_id = f"service_{service.id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    cron_parts = service.cron.strip().split()
    if len(cron_parts) == 5:
        cron_full = service.cron.strip()
    elif len(cron_parts) < 5:
        cron_full = " ".join(cron_parts + ["*"] * (5 - len(cron_parts)))
    else:
        raise ValueError(f"Invalid cron format '{service.cron}' (must have 5 fields)")

    try:
        trigger = CronTrigger.from_crontab(cron_full)
        scheduler.add_job(
            func=check_service_job,
            trigger=trigger,
            args=[service.id, app],  
            id=job_id,
            replace_existing=True
        )
    except Exception as e:
        print(f"[ERROR] Failed to add cron for service ID {service.id}: {e}")



