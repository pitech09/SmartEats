# utils/notifications.py
from ..models import Notification, db
from datetime import datetime

def create_notification(user_type, user_id, message):
    notification = Notification(
        user_type=user_type,
        user_id=user_id,
        message=message,
        timestamp=datetime.utcnow(),
        is_read=False
    )
    db.session.add(notification)
    db.session.commit()
