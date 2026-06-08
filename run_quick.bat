@echo off
echo ============================================
echo  Quick Mode: Planning + Script Only
echo ============================================
python main.py --genre "%~1" --episodes %~2 %~3 %~4 %~5 %~6
pause
