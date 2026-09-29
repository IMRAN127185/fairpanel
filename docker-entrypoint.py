import os
import sys
import subprocess
import secrets
from pathlib import Path

def run_cmd(cmd):
    print(f"--> {cmd}")
    res = subprocess.run(cmd, shell=True)
    if res.returncode != 0:
        print(f"Command failed with code {res.returncode}")
        sys.exit(res.returncode)

def main():
    print("=== Starting FairPanel ===")
    if not os.environ.get('DJANGO_SECRET_KEY'):
        secret_file = Path(os.environ.get('FAIRPANEL_SECRET_FILE', '/app/data/secret-key'))
        secret_file.parent.mkdir(parents=True, exist_ok=True)
        if not secret_file.exists():
            secret_file.write_text(secrets.token_urlsafe(64), encoding='utf-8')
            try:
                secret_file.chmod(0o600)
            except OSError:
                pass
        os.environ['DJANGO_SECRET_KEY'] = secret_file.read_text(encoding='utf-8').strip()
    run_cmd("python manage.py migrate --noinput")
    run_cmd("python manage.py seed_fixtures")
    
    port = os.environ.get("PORT", "8080")
    print(f"=== Serving on http://0.0.0.0:{port} ===")
    os.execv(sys.executable, [sys.executable, "manage.py", "runserver", f"0.0.0.0:{port}"])

if __name__ == "__main__":
    main()
