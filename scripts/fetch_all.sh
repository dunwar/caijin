#!/bin/bash
# caijin.gaozhong.online — 每日数据采集主脚本
# cron: 0 16 * * * (UTC 16:00 = 北京时间 00:00)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_FILE="$SCRIPT_DIR/../data/fetch.log"

echo "=== $(date '+%Y-%m-%d %H:%M:%S') 开始数据采集 ===" >> "$LOG_FILE"

echo "[1/3] 白酒板块..." >> "$LOG_FILE"
python3 "$SCRIPT_DIR/fetch_baijiu.py" >> "$LOG_FILE" 2>&1

echo "[2/3] AI硬件..." >> "$LOG_FILE"
python3 "$SCRIPT_DIR/fetch_hardware.py" >> "$LOG_FILE" 2>&1

echo "[3/3] AI软件..." >> "$LOG_FILE"
python3 "$SCRIPT_DIR/fetch_software.py" >> "$LOG_FILE" 2>&1

echo "=== 采集完成 ===" >> "$LOG_FILE"
