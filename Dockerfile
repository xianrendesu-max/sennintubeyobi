# 軽量なPythonイメージを使用
FROM python:3.11-slim

# 作業ディレクトリの設定
WORKDIR /app

# システム依存パッケージのインストール（lxmlのビルドなどに必要な場合があるため）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 依存ライブラリのコピーとインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションソースのコピー
# (templates, css, blog フォルダも一緒にコピーされます)
COPY . .

# Flaskが使用するポートの開放
EXPOSE 8000

# 環境変数の設定（Pythonのバッファを無効化してログをリアルタイム表示）
ENV PYTHONUNBUFFERED=1

# 実行コマンド
# 注意: main.py内の app.run() が実行されます。
# 本番環境では本来 gunicorn 等の使用が推奨されますが、
# main.py の末尾の構成に合わせて python で起動します。
CMD ["python", "main.py"]
