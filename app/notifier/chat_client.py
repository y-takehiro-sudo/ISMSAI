"""Google Chat 送信クライアント。
Webhook方式（推奨）とサービスアカウント方式の両対応。
GOOGLE_CHAT_WEBHOOK_URL が設定されていればWebhookを使用する。
"""
import logging
import os

import httpx
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────
# Webhook方式（自分のGoogleアカウントで設定可能）
# ────────────────────────────────────────────────

def _send_webhook(webhook_url: str, message: str) -> bool:
    """Incoming Webhookでメッセージを送信する。"""
    try:
        resp = httpx.post(
            webhook_url,
            json={"text": message},
            timeout=10,
        )
        if resp.status_code == 200:
            logger.info("Google Chat Webhook 送信成功")
            return True
        else:
            logger.error(f"Webhook 送信失敗 {resp.status_code}: {resp.text[:200]}")
            return False
    except Exception as e:
        logger.error(f"Webhook 送信例外: {e}")
        return False


# ────────────────────────────────────────────────
# サービスアカウント方式（Bot、IT管理者権限が必要）
# ────────────────────────────────────────────────

def _get_access_token():
    creds_path = os.getenv("GOOGLE_CHAT_CREDENTIALS_JSON", "./credentials.json")
    if not os.path.exists(creds_path):
        return None
    try:
        from google.oauth2 import service_account
        import google.auth.transport.requests
        creds = service_account.Credentials.from_service_account_file(
            creds_path, scopes=["https://www.googleapis.com/auth/chat.bot"]
        )
        creds.refresh(google.auth.transport.requests.Request())
        return creds.token
    except Exception as e:
        logger.error(f"サービスアカウント認証失敗: {e}")
        return None


def _send_service_account(space_id: str, message: str) -> bool:
    token = _get_access_token()
    if not token:
        return False
    url = f"https://chat.googleapis.com/v1/{space_id}/messages"
    try:
        resp = httpx.post(
            url,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"text": message},
            timeout=10,
        )
        if resp.status_code == 200:
            logger.info(f"サービスアカウント送信成功: {space_id}")
            return True
        else:
            logger.error(f"サービスアカウント送信失敗 {resp.status_code}: {resp.text[:200]}")
            return False
    except Exception as e:
        logger.error(f"サービスアカウント送信例外: {e}")
        return False


# ────────────────────────────────────────────────
# 統合インターフェース（Webhookを優先）
# ────────────────────────────────────────────────

def send_notification(target_user_id: str, space_type: str, message: str,
                      user_google_id: str = None) -> bool:
    """
    通知を送信する。
    space_type:
      "member" → メンバー向けスペース
      "admin"  → 管理者向けスペース
      "dm"     → 個人メンション（メンバースペースに投稿）
      "group"  → 後方互換（メンバースペース扱い）
    """
    webhook_member = os.getenv("GOOGLE_CHAT_WEBHOOK_MEMBER", "")
    webhook_admin  = os.getenv("GOOGLE_CHAT_WEBHOOK_ADMIN", "")
    # 旧設定の後方互換
    webhook_legacy = os.getenv("GOOGLE_CHAT_WEBHOOK_URL", "")

    # 送信先スペースを決定
    if space_type == "admin":
        webhook_url = webhook_admin or webhook_member or webhook_legacy
    else:
        # member / dm / group → メンバースペース
        webhook_url = webhook_member or webhook_legacy

    if not webhook_url:
        logger.warning(f"Webhook URL 未設定: space_type={space_type}")
        return False

    # メンション生成
    if user_google_id:
        mention = f"<{user_google_id}> "   # 個人メンション
    else:
        mention = "<users/all> "            # 全体メンション

    return _send_webhook(webhook_url, f"{mention}{message}")
