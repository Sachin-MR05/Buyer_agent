@echo off
set ROOT=%~dp0

start "Buyer Agent Backend" powershell -NoExit -WorkingDirectory "%ROOT%buyer-agent-core" -Command "& \"%ROOT%.venv\Scripts\python.exe\" -m uvicorn main:app --reload --port 8010"
start "Buyer Agent Frontend" powershell -NoExit -WorkingDirectory "%ROOT%buyer-agent-frontend" -Command "npm run dev"

echo Buyer Agent services started.
echo Backend: http://localhost:8010
echo Frontend: http://localhost:5173
