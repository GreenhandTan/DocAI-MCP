@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo =========================================
echo   DocAI-MCP 系统部署脚本 (Windows)
echo =========================================
echo.

:: 切换到脚本所在目录
cd /d "%~dp0"

:: 检查 .env 文件是否存在
if not exist ".env" (
    echo [错误] 未找到 .env 配置文件
    echo 请先复制 .env.example 到 .env 并配置相关参数
    echo.
    pause
    exit /b 1
)

:: 检查 Docker 是否安装
where docker >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Docker，请先安装 Docker Desktop
    echo 下载地址: https://www.docker.com/products/docker-desktop
    echo.
    pause
    exit /b 1
)

:: 检查 Docker 是否运行
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] Docker 未运行，请先启动 Docker Desktop
    echo.
    pause
    exit /b 1
)

:: 检查 docker-compose 是否可用
docker compose version >nul 2>&1
if %errorlevel% neq 0 (
    docker-compose version >nul 2>&1
    if %errorlevel% neq 0 (
        echo [错误] 未找到 docker-compose，请确保 Docker Desktop 已正确安装
        echo.
        pause
        exit /b 1
    )
    set COMPOSE_CMD=docker-compose
) else (
    set COMPOSE_CMD=docker compose
)

echo [信息] 使用命令: %COMPOSE_CMD%
echo.

echo 步骤 1/5: 清理旧容器和镜像...
if "%RESET_VOLUMES%"=="1" (
    %COMPOSE_CMD% down -v
) else (
    %COMPOSE_CMD% down
)
if %errorlevel% neq 0 (
    echo [警告] 清理过程中出现问题，继续执行...
)
echo.

echo 步骤 2/5: 构建镜像...
%COMPOSE_CMD% build
if %errorlevel% neq 0 (
    echo [错误] 镜像构建失败
    echo.
    pause
    exit /b 1
)
echo.

echo 步骤 3/5: 启动服务...
%COMPOSE_CMD% up -d
if %errorlevel% neq 0 (
    echo [错误] 服务启动失败
    echo.
    pause
    exit /b 1
)
echo.

echo 步骤 4/5: 等待服务启动...
echo 请稍候，正在等待服务初始化 (10秒)...
timeout /t 10 /nobreak >nul
echo.

echo 步骤 5/5: 检查服务状态...
%COMPOSE_CMD% ps
echo.

echo =========================================
echo   部署完成！
echo =========================================
echo.
echo 服务访问地址：
echo   - 前端界面:    http://localhost:3000
echo   - 后端API:     http://localhost:8000
echo   - MinIO控制台: http://localhost:9001
echo   - OnlyOffice:  http://localhost:8081
echo.
echo 常用命令：
echo   查看日志:  %COMPOSE_CMD% logs -f [service_name]
echo   停止服务:  %COMPOSE_CMD% down
echo   重启服务:  %COMPOSE_CMD% restart
echo.

pause
