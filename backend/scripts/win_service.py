"""
Windows service wrapper for the Project SC backend (FastAPI + APScheduler).

Requires: pip install pywin32

Install (run from backend dir as Administrator):
  python scripts\win_service.py install

Start:
  python scripts\win_service.py start

Stop:
  python scripts\win_service.py stop

Remove:
  python scripts\win_service.py remove
"""

import os
import subprocess
import sys
import time

# Resolve backend directory (parent of scripts/)
_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_VENV_PYTHON = os.path.join(_BACKEND_DIR, "venv", "Scripts", "python.exe")
_PYTHON = _VENV_PYTHON if os.path.isfile(_VENV_PYTHON) else sys.executable

try:
    import win32serviceutil
    import win32service
    import win32event
    import win32api
except ImportError:
    print("pywin32 is required. Run: pip install pywin32", file=sys.stderr)
    sys.exit(1)


class ProjectSCBackendService(win32serviceutil.ServiceFramework):
    _svc_name_ = "ProjectSCBackend"
    _svc_display_name_ = "Project SC Backend API"
    _svc_description_ = (
        "FastAPI backend and APScheduler for Project SC (scheduled POs)."
    )

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.process = None

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()

    def SvcDoRun(self):
        os.chdir(_BACKEND_DIR)
        self.process = subprocess.Popen(
            [
                _PYTHON,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "0.0.0.0",
                "--port",
                "8000",
            ],
            cwd=_BACKEND_DIR,
            env=dict(os.environ),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        while True:
            if (
                win32event.WaitForSingleObject(self.stop_event, 1000)
                == win32event.WAIT_OBJECT_0
            ):
                break
            if self.process.poll() is not None:
                break
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()


if __name__ == "__main__":
    win32serviceutil.HandleCommandLine(ProjectSCBackendService)
