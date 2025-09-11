@echo off
setlocal
if "%~1"=="" (
  echo Usage: smoke_prod.bat https://<service>.onrender.com [X-Token]
  exit /b 64
)
set "BASE=%~1"
set "TOKEN=%~2"
if "%TOKEN%"=="" set "TOKEN=%INTERNAL_TOKEN%"

echo BASE=%BASE%
curl.exe -s -o NUL -w "HEALTH %%{http_code}\n" "%BASE%/health"
curl.exe -s -o NUL -w "SEND %%{http_code}\n" -X POST "%BASE%/internal/send?format=text" ^
 -H "X-Token: %TOKEN%" -H "Content-Type: application/json" ^
 -d "{\"text\":\"ping\"}"
curl.exe -s -o NUL -w "CHECKIN %%{http_code}\n" -X POST "%BASE%/internal/checkin" ^
 -H "X-Token: %TOKEN%" -H "Content-Type: application/json" ^
 -d "{\"dry_run\":true}"
