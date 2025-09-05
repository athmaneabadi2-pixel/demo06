@echo off
cd /d %~dp0
if not exist .venv\Scripts\activate.bat (
  py -m venv .venv
  call .venv\Scripts\activate
  pip install -r requirements.txt
) else (
  call .venv\Scripts\activate
)
set FLASK_ENV=development
python app.py
