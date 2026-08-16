@echo off
cd /d "%~dp0"
python -m hdl_x.gui.main
if errorlevel 1 pause
