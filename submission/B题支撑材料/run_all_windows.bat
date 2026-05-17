@echo off
python -m venv .venv
call .\.venv\Scripts\activate
pip install -r requirements.txt
python scripts\run_problem1.py
python scripts\run_problem2.py
python scripts\run_problem34.py
pause
