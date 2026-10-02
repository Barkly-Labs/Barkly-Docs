@echo off
if "%~1"=="" (
  echo Usage: run-barkly-audit.bat PATH_TO_GENERATED_OUTPUT
  exit /b 2
)
python -m tools.barkly_audit "%~1"
exit /b %ERRORLEVEL%
