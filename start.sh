#!/bin/bash
# WebZFS 一键启动脚本 (监听端口 5300)
# 用法: ./start.sh
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

export HOME="$SCRIPT_DIR"
export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"

# 首次运行自动安装依赖
if [ ! -d ".venv" ]; then
    echo "首次运行，创建 Python 虚拟环境..."
    PYTHON=$(command -v python3.12 || command -v python3)
    "$PYTHON" -m venv .venv
    .venv/bin/pip install --upgrade pip -q
    .venv/bin/pip install -r requirements.txt -q
fi

if [ ! -d "node_modules" ]; then
    echo "首次运行，安装 Node.js 依赖并构建静态资源..."
    npm install --no-audit --no-fund
    mkdir -p static/css
    npm run build:css
fi

# 生成 .env（如不存在），并确保监听所有网络接口
if [ ! -f ".env" ]; then
    SECRET=$(.venv/bin/python3 -c "import secrets; print(secrets.token_hex(32))")
    sed -e "s/CHANGE_ME_GENERATE_NEW_KEY/${SECRET}/" \
        -e "s/^PORT=26619/PORT=5300/" .env.example > .env
fi
sed -i "s/^BIND_IP=.*/BIND_IP=0.0.0.0/" .env

# 初始化数据目录
DATA_DIR=".config/webzfs"
mkdir -p "$DATA_DIR/progress" "$DATA_DIR/logs"
[ -f "$DATA_DIR/replication_history.json" ] || echo '{"executions": [], "next_id": 1}' > "$DATA_DIR/replication_history.json"
[ -f "$DATA_DIR/notification_log.json" ]     || echo '{"notifications": []}' > "$DATA_DIR/notification_log.json"
[ -f "$DATA_DIR/syncoid_jobs.json" ]         || echo '{"jobs": [], "next_id": 1}' > "$DATA_DIR/syncoid_jobs.json"
[ -f "$DATA_DIR/scrub_schedules.json" ]      || echo '{"schedules": []}' > "$DATA_DIR/scrub_schedules.json"
[ -f "$DATA_DIR/smart_test_history.json" ]   || echo '{"history": []}' > "$DATA_DIR/smart_test_history.json"
[ -f "$DATA_DIR/scheduled_tests.json" ]      || echo '{}' > "$DATA_DIR/scheduled_tests.json"

PORT=$(grep -E '^PORT=' .env | cut -d= -f2)
BIND_IP=$(grep -E '^BIND_IP=' .env | cut -d= -f2)
echo "WebZFS 启动中: http://${BIND_IP:-127.0.0.1}:${PORT:-5300}"

# 后台常驻请将下面 exec 行替换为:
#   nohup .venv/bin/gunicorn -c config/gunicorn.conf.py > webzfs.log 2>&1 &
exec .venv/bin/gunicorn -c config/gunicorn.conf.py
