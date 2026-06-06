"""Start backend and frontend servers."""
import subprocess, os, time

os.chdir("/Users/m4max/VS-CODE-PROJECT/GatherInfo")

# Start backend
bl = open("logs/backend.log", "w")
bp = subprocess.Popen(
    ["backend/.venv/bin/python", "-m", "uvicorn", "app.main:create_app",
     "--factory", "--host", "127.0.0.1", "--port", "8109", "--app-dir", "backend"],
    stdout=bl, stderr=subprocess.STDOUT,
    start_new_session=True
)
print(f"Backend PID={bp.pid} on port 8109", flush=True)
time.sleep(2)

# Verify backend
h = subprocess.run(["curl", "-s", "--max-time", "3", "http://127.0.0.1:8109/health"],
                    capture_output=True, text=True)
print(f"Backend health: {h.stdout.strip() or h.stderr[:60]}", flush=True)

# Start frontend
fl = open("logs/frontend.log", "w")
fp = subprocess.Popen(
    ["/opt/homebrew/bin/npm", "--prefix", "frontend", "run", "dev",
     "--", "--host", "127.0.0.1", "--port", "5178"],
    stdout=fl, stderr=subprocess.STDOUT,
    start_new_session=True
)
print(f"Frontend PID={fp.pid} on port 5178", flush=True)
time.sleep(3)

# Verify frontend
h2 = subprocess.run(["curl", "-s", "--max-time", "3", "http://127.0.0.1:5178/"],
                     capture_output=True, text=True)
has_root = "root" in h2.stdout
print(f"Frontend HTML: {'OK' if has_root else 'issue'}", flush=True)

# Keep alive
print("\n--- Both servers running. Press Ctrl+C to stop ---", flush=True)
try:
    while True:
        time.sleep(10)
        # Check both are alive
        if not subprocess.run(["kill", "-0", str(bp.pid)],
                               capture_output=True).returncode == 0:
            print("BACKEND DIED!", flush=True)
            break
        if not subprocess.run(["kill", "-0", str(fp.pid)],
                               capture_output=True).returncode == 0:
            print("FRONTEND DIED!", flush=True)
            break
except KeyboardInterrupt:
    bp.kill()
    fp.kill()
    print("Servers stopped", flush=True)
