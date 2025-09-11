@echo off
setlocal EnableExtensions EnableDelayedExpansion
REM --- profile_check.bat V7 (root=instances, ignore .venv, BOM-safe) ---

REM 0) Dossier du script (ex: ...\instances\demo06\ops\)
set "SCRIPT_DIR=%~dp0"

REM 1) ROOT par défaut = ..\..\ (le dossier "instances")
for %%A in ("%SCRIPT_DIR%\..\..") do set "ROOT=%%~fA"

REM 2) Si un argument est fourni, on l'utilise (absolutisé)
if not "%~1"=="" (
  for %%A in ("%~1") do set "ROOT=%%~fA"
)

set /a PASS=0
set /a FAIL=0
set /a COUNT=0

REM 3) Lister UNIQUEMENT des fichiers profile.json sous ROOT, exclure .venv
for /f "usebackq delims=" %%F in (`
  dir /b /s /a:-d "%ROOT%\profile.json" 2^>NUL ^| findstr /I /V "\\.venv\\"
`) do (
  set "FILE=%%~fF"
  if not exist "!FILE!" (
    echo [SKIP] !FILE! -- missing file
  ) else (
    set /a COUNT+=1
    set "RES=PY_ERROR"
    for /f "usebackq delims=" %%R in (`
      python -c "import json,sys,io;p=sys.argv[1];d=json.load(io.open(p,'r',encoding='utf-8-sig'));print('OK' if isinstance(d.get('user'),dict) and d['user'].get('display_name') else 'MISSING:user.display_name')" "!FILE!" 2^>NUL
    `) do set "RES=%%R"

    if /I "!RES!"=="OK" (
      echo [OK] !FILE!
      set /a PASS+=1
    ) else (
      if /I "!RES!"=="PY_ERROR" (
        echo [FAIL] !FILE! -- JSON_ERROR
      ) else (
        echo [FAIL] !FILE! -- !RES!
      )
      set /a FAIL+=1
    )
  )
)

if %COUNT%==0 (
  echo No profile.json found under "%ROOT%".
  exit /b 0
)

echo ----
echo Profiles OK: %PASS%   Profiles FAIL: %FAIL%
if %FAIL% GTR 0 exit /b 1
exit /b 0
