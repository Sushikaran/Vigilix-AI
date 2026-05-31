# Vigilix AI - GitHub Ready Project

Upload this project as normal files/folders to GitHub. Do not upload it as one zip inside GitHub.

## Upload to GitHub

```bash
git init
git add .
git commit -m "Initial Vigilix AI project"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/vigilix-ai.git
git push -u origin main
```

## Files intentionally ignored

The included `.gitignore` prevents uploading:

- `venv/`
- `.env`
- `*.db`
- `evidence/`
- `__pycache__/`
- large model weights such as `models/*.pt`

Keep `.env.example` on GitHub, but keep your real `.env` private.

## Run locally

```bash
python -m venv venv
venv\Scripts\activate
python -m pip install -r requirements.txt
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

## Deploy on Render

Use:

```text
Build Command: pip install -r requirements.txt
Start Command: gunicorn app:app
```

Add environment variables in Render dashboard instead of uploading `.env`.
