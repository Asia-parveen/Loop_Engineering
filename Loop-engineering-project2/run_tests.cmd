@echo off
python -m unittest discover -s tests -v
exit /b %errorlevel%
