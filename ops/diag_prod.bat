@echo off
setlocal
if "%~1"=="" (
  echo Usage: diag_prod.bat https://<service>.onrender.com [X-Token]
  exit /b 64
)
set "BASE=%~1"
set "TOKEN=%~2"
if "%TOKEN%"=="" set "TOKEN=%INTERNAL_TOKEN%"

echo === Reachability (HEAD /health)
curl.exe -I "%BASE%/health" || (echo Network error & exit /b 1)
echo.

echo === /health (first 400 chars)
curl.exe -s "%BASE%/health" | python -c "import sys;print(sys.stdin.read()[:400])"
echo.

echo === internal/checkin (dry_run)
curl.exe -s -o NUL -w "CHECKIN %%{http_code}\n" -X POST "%BASE%/internal/checkin" ^
 -H "X-Token: %TOKEN%" -H "Content-Type: application/json" ^
 -d "{\"dry_run\":true}"

echo === webhook synthetic form (does not require secrets)
REM Uses env placeholders if set: USER_WHATSAPP_TO / TWILIO_SANDBOX_FROM
curl.exe -s -o NUL -w "WEBHOOK %%{http_code}\n" -X POST "%BASE%/whatsapp/webhook" ^
 -H "Content-Type: application/x-www-form-urlencoded" ^
 --data "MessageSid=SM-DIAG-TEST&From=whatsapp:%USER_WHATSAPP_TO%&To=%TWILIO_SANDBOX_FROM%&Body=ping&AccountSid=ACxxxxxxxx"
echo Tip: If WEBHOOK is 401/403, check VERIFY_TWILIO_SIGNATURE and PUBLIC_WEBHOOK_URL on Render.
