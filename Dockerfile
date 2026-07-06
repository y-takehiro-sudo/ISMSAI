# ─────────────────────────────────────────────
# ISMS PDCAシステム - Dockerfile
# ─────────────────────────────────────────────
FROM python:3.11-slim

# タイムゾーン設定（日本時間）
ENV TZ=Asia/Tokyo
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# 作業ディレクトリ
WORKDIR /app

# 依存ライブラリをインストール（キャッシュ効率のためrequirements.txtを先にコピー）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコードをコピー
COPY . .

# ログ・アップロードディレクトリを作成
RUN mkdir -p logs uploads

# 起動ポート
EXPOSE 8000

# 起動コマンド
# main.py の __main__ ではなく uvicorn を直接呼び出す（本番推奨）
CMD ["python", "-m", "uvicorn", "main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--log-level", "info"]
