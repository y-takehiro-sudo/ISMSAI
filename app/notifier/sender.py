"""notification_queue の approved レコードを実際に送信する処理。"""
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import NotificationQueue, User
from app.notifier.chat_client import send_notification

logger = logging.getLogger(__name__)


def flush_approved_queue(db: Session) -> int:
    """status=approved のキューを送信してstatus=sentに更新する。送信件数を返す。"""
    items = (
        db.query(NotificationQueue)
        .filter(NotificationQueue.status == "approved")
        .all()
    )

    sent = 0
    for item in items:
        user = db.query(User).filter(User.id == item.target_user_id).first()
        google_id = user.google_chat_user_id if user else None

        try:
            ok = send_notification(
                target_user_id=item.target_user_id,
                space_type=item.space_type,
                message=item.message_body,
                user_google_id=google_id,
            )
            if ok:
                item.status = "sent"
                item.sent_at = datetime.now().isoformat()
                sent += 1
                logger.info(f"通知送信完了: queue_id={item.id}")
            else:
                logger.error(f"通知送信失敗: queue_id={item.id}")
        except Exception as e:
            logger.error(f"通知送信例外: queue_id={item.id}, error={e}")

    db.commit()
    return sent
