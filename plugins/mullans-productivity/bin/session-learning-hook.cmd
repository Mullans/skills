@echo off
setlocal
set "POWERSHELL_EXE=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%POWERSHELL_EXE%" exit /b 0
"%POWERSHELL_EXE%" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%~dp0session-learning-hook.ps1" %*
rem Retrieval is advisory. Never propagate a launcher failure to the host.
exit /b 0
