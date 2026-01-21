#!/bin/bash

set -e

echo "========================================="
echo "  DocAI-MCP 系统部署脚本"
echo "========================================="
echo ""

cd "$(dirname "$0")"

if [ ! -f ".env" ]; then
    echo "错误：未找到 .env 配置文件"
    echo "请先复制 .env.example 到 .env 并配置相关参数"
    exit 1
fi

echo "步骤 1/5: 清理旧容器和镜像..."
if [ "${RESET_VOLUMES:-}" = "1" ]; then
    docker-compose down -v
else
    docker-compose down
fi

echo ""
echo "步骤 2/5: 构建镜像..."
docker-compose build

echo ""
echo "步骤 3/5: 启动服务..."
docker-compose up -d

echo ""
echo "步骤 4/5: 等待服务启动..."
sleep 10

echo ""
echo "步骤 5/5: 检查服务状态..."
docker-compose ps

echo ""
echo "========================================="
echo "  部署完成！"
echo "========================================="
echo ""
echo "服务访问地址："
echo "  - 前端界面: http://localhost:3000"
echo "  - 后端API:  http://localhost:8000"
echo "  - MinIO控制台: http://localhost:9001"
echo "  - OnlyOffice: http://localhost:8081"
echo ""
echo "查看日志："
echo "  docker-compose logs -f [service_name]"
echo ""
echo "停止服务："
echo "  docker-compose down"
echo ""
