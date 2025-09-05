@echo off
setlocal
echo [Smoke] Test /health...
curl.exe -s http://127.0.0.1:5000/health | find "\"status\":\"ok\"" >nul || (echo [X] /health KO & exit /b 1)
echo [Smoke] Test /internal/send...
curl.exe -s -X POST http://127.0.0.1:5000/internal/send -H "Content-Type: application/json" -d "{\"text\":\"Salut\"}" | find "\"ok\": true" >nul || (echo [X] /internal/send KO & exit /b 1)
echo [OK] Smoke test passe.
exit /b 0
