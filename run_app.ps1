# Launcher for Streamlit Web UI using Python module entry point
# Compatible with Windows Application Control, WDAC, and AppLocker policies
Write-Host "Launching IT Vendor Renewal Decision Support Agent UI..." -ForegroundColor Cyan
& ".\.venv\Scripts\python.exe" -m streamlit run app.py
