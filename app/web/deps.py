"""共通依存・プロジェクトパス定義。

各ルーターで重複していた Jinja2Templates の初期化をここに集約する。
使い方:
    from app.web.deps import templates, UPLOAD_DIR
"""
import os
from fastapi.templating import Jinja2Templates

# app/web/deps.py から2階層上がプロジェクトルート
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

templates = Jinja2Templates(directory=os.path.join(_PROJECT_ROOT, "templates"))
UPLOAD_DIR = os.path.join(_PROJECT_ROOT, "uploads")
