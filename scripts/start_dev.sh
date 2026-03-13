#!/bin/bash
# 开发环境一键启动脚本

echo "=== NUS Campus Intelligent Assistant ==="
echo "Powered by OpenClaw + WaveSpeed AI"
echo ""

# 检查 .env
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env from template. Please fill in your API keys!"
    exit 1
fi

# 启动后端
echo "[1/3] Starting FastAPI backend..."
cd backend
pip install -r requirements.txt -q
uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!
cd ..

# 等待后端启动
sleep 3

# 摄入知识库（首次运行）
if [ ! -d "data/chroma_db" ] || [ -z "$(ls -A data/chroma_db 2>/dev/null)" ]; then
    echo "[2/3] First run: ingesting NUS knowledge base..."
    python scripts/ingest_knowledge.py
else
    echo "[2/3] Knowledge base exists, skipping ingestion"
fi

# 启动前端
echo "[3/3] Starting React frontend..."
cd frontend
npm install -q
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "=== Ready! ==="
echo "Frontend: http://localhost:5173"
echo "Backend API: http://localhost:8000"
echo "API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop all services"

wait $BACKEND_PID $FRONTEND_PID
