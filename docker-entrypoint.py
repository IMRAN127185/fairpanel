import os
import sys
import subprocess

def run_cmd(cmd):
    print(f"--> {cmd}")
    res = subprocess.run(cmd, shell=True)
    if res.returncode != 0:
        print(f"Command failed with code {res.returncode}")
        sys.exit(res.returncode)

def main():
    print("=== Starting FairPanel ===")
    run_cmd("python manage.py migrate --noinput")
    run_cmd("python manage.py seed_fixtures")
    
    port = os.environ.get("PORT", "8080")
    print(f"=== Serving on http://0.0.0.0:{port} ===")
    os.execv(sys.executable, [sys.executable, "manage.py", "runserver", f"0.0.0.0:{port}"])

if __name__ == "__main__":
    main()
