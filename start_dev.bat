@echo off
chcp 65001 >nul
title AI 爆文智能创作平台 - 后端服务
echo ============================================
echo  AI 爆文智能创作平台 - 后端服务
echo ============================================
echo.

REM 检查 Redis 是否已启动
"D:\Redis\redis\redis-cli.exe" -p 16379 ping >nul 2>&1
if errorlevel 1 (
    echo [Redis] 未运行，正在启动...
    start "" /B "D:\Redis\redis\redis-server.exe" --port 16379 --bind 127.0.0.1 --save "" --appendonly no --protected-mode no
    timeout /t 2 /nobreak >nul
) else (
    echo [Redis] 已在 16379 端口运行
)

echo [服务] 启动 FastAPI (http://127.0.0.1:8001)
echo [文档] http://127.0.0.1:8001/docs
echo.
"E:\miniconda3\envs\fastapi_env\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8001

pause
