#!/bin/bash
cd "$(dirname "$0")"
echo "正在安装免费行情源依赖 akshare pandas..."
python3 -m pip install akshare pandas --break-system-packages
echo ""
echo "安装完成。按回车键关闭窗口..."
read
