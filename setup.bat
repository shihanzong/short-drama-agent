@echo off
echo ============================================
echo  Short Drama Agent - Setup
echo ============================================
echo.

echo [1/3] Checking Python...
python --version 2>nul || echo ERROR: Python not found
echo.

echo [2/3] Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: pip install failed
    pause
    exit /b 1
)
echo.

echo [3/3] Verifying setup...
python -c "from modules.llm_client import LLMClient; print('LLMClient: OK')" 2>nul
python -c "from modules.tts_engine import TTSEngine; print('TTSEngine: OK')" 2>nul
python -c "from agents.creative_planner import CreativePlannerAgent; print('CreativePlannerAgent: OK')" 2>nul
echo.

echo Setup complete!
echo.
echo Quick test:
echo   python main.py --genre "重生复仇" --episodes 3 --mode quick
echo.
pause
