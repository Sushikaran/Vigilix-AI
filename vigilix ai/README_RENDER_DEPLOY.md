# Deploy Vigilix AI on Render

Upload the CONTENTS of this folder to GitHub. Do not upload the ZIP file itself.

Your GitHub root must directly contain:

```text
app.py
requirements.txt
Procfile
runtime.txt
templates/
static/
utils/
```

Render settings:

```text
Build Command: pip install -r requirements.txt
Start Command: gunicorn app:app
```

Add environment variables in Render instead of uploading `.env`:

```text
ROBOFLOW_API_KEY
WEAPON_MODEL_ID
FIRE_SMOKE_MODEL_ID
SMTP_EMAIL
SMTP_PASSWORD
```

After changing files in GitHub, redeploy on Render using Clear build cache & deploy.
