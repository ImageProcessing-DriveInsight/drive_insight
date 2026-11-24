@echo off
cd /d "%~dp0"
py -m pytest -q tests/test_video_io.py tests/test_b_adaptive.py tests/test_b_data.py tests/test_b_package.py tests/test_b_sensitivity.py tests/test_b_status.py
if errorlevel 1 (
  echo Tests failed. Check the error output above.
) else (
  echo B tests passed.
)
pause
