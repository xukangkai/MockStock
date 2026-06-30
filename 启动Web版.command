#!/bin/bash
cd "$(dirname "$0")"
echo "================================================"
echo "  A股全自动智能交易系统"
echo "================================================"
echo ""
echo "检查依赖..."
pip3 install pymysql akshare pandas numpy fastapi uvicorn sqlalchemy python-multipart -q 2>/dev/null
echo ""
echo "正在启动服务..."
echo "启动后请在浏览器中打开：http://127.0.0.1:8080"
echo "按 Ctrl+C 停止"
echo ""
python3 web_app.py
