#!/bin/bash
# caijin.gaozhong.online 部署脚本
set -e

SRC="/home/node/.openclaw/workspace/www/caijin.gaozhong.online"
DEST="/app/data/www/caijin.gaozhong.online"
NGINX_SRC="$SRC/nginx.conf"
NGINX_DEST="/app/data/nginx-configs/caijin.gaozhong.online.conf"

echo "=== 部署 caijin.gaozhong.online ==="

# 1. 复制文件到生产目录
echo "[1/4] 复制文件..."
mkdir -p "$DEST/data/baijiu" "$DEST/data/hardware" "$DEST/data/software" "$DEST/scripts"
cp "$SRC"/*.html "$DEST/"
cp "$SRC/scripts/"*.py "$DEST/scripts/"
cp "$SRC/scripts/fetch_all.sh" "$DEST/scripts/"

# 2. 安装 Nginx 配置
echo "[2/4] 部署 Nginx 配置..."
cp "$NGINX_SRC" "$NGINX_DEST"

# 3. 配置 cron（每日采集）
echo "[3/4] 配置 cron..."
CRON_CMD="cd $SRC && bash scripts/fetch_all.sh"
# 注意: 容器内无 crontab，实际采集 cron 配置在宿主机；此处失败不阻断部署
(crontab -l 2>/dev/null | grep -v "fetch_all.sh"; echo "0 16 * * * $CRON_CMD") | crontab - 2>/dev/null || echo "  (容器内无 crontab，跳过 — 请确认宿主机 cron 存在)"

# 4. 测试数据脚本
echo "[4/4] 测试数据脚本..."
cd "$DEST"
python3 scripts/fetch_baijiu.py 2>&1 | tail -1
python3 scripts/fetch_hardware.py 2>&1 | tail -1
python3 scripts/fetch_software.py 2>&1 | tail -1

echo ""
echo "=== 部署完成 ==="
echo "请手动执行: sudo nginx -s reload"
echo "访问: http://caijin.gaozhong.online"
