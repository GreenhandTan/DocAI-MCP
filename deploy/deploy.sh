#!/bin/bash

set -Eeuo pipefail

echo "========================================="
echo "  DocAI-MCP 系统部署脚本"
echo "========================================="
echo ""

cd "$(dirname "$0")"

# 兼容 docker compose / docker-compose
if docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
else
    echo "错误：未检测到 docker compose 或 docker-compose"
    exit 1
fi

# 构建失败重试次数（默认 2 次）
BUILD_RETRY="${BUILD_RETRY:-2}"
# 国内服务器默认使用国内源
USE_CN_MIRROR="${USE_CN_MIRROR:-1}"
PIP_INDEX_URL="${PIP_INDEX_URL:-https://mirrors.aliyun.com/pypi/simple/}"
# 默认不强制拉取基础镜像，避免网络波动导致构建失败
PULL_BASE_IMAGES="${PULL_BASE_IMAGES:-0}"

if [ ! -f ".env" ]; then
    echo "错误：未找到 .env 配置文件"
    echo "请先复制 .env.example 到 .env 并配置相关参数"
    exit 1
fi

echo "步骤 1/5: 清理旧容器和镜像..."
if [ "${RESET_VOLUMES:-}" = "1" ]; then
    ${COMPOSE_CMD} down -v
else
    ${COMPOSE_CMD} down
fi

echo ""
echo "步骤 2/5: 构建镜像..."
echo "构建参数: USE_CN_MIRROR=${USE_CN_MIRROR}, PIP_INDEX_URL=${PIP_INDEX_URL}"
build_success=0
for attempt in $(seq 1 "${BUILD_RETRY}"); do
    echo "构建尝试 ${attempt}/${BUILD_RETRY}..."
    build_cmd="${COMPOSE_CMD} build"
    if [ "${PULL_BASE_IMAGES}" = "1" ]; then
        build_cmd="${build_cmd} --pull"
    fi

    if ${build_cmd} \
        --build-arg USE_CN_MIRROR="${USE_CN_MIRROR}" \
        --build-arg PIP_INDEX_URL="${PIP_INDEX_URL}"; then
        build_success=1
        break
    fi
    echo "构建失败：第 ${attempt} 次尝试未成功"
    if [ "${attempt}" -lt "${BUILD_RETRY}" ]; then
        echo "等待 10 秒后重试..."
        sleep 10
    fi
done

if [ "${build_success}" -ne 1 ]; then
    echo "错误：镜像构建失败，请检查网络连通性和镜像源配置"
    echo "提示：可尝试 BUILD_RETRY=3，或临时开启 PULL_BASE_IMAGES=1 后重试"
    exit 1
fi

echo ""
echo "步骤 3/5: 启动服务..."
${COMPOSE_CMD} up -d

echo ""
echo "步骤 4/5: 等待服务启动..."
sleep 10

echo ""
echo "步骤 5/5: 检查服务状态..."
${COMPOSE_CMD} ps

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
echo "  ${COMPOSE_CMD} logs -f [service_name]"
echo ""
echo "停止服务："
echo "  ${COMPOSE_CMD} down"
echo ""
