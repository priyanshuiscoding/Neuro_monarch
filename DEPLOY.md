# Deploy NeuroMonarch

## 1) Required Environment Variables

Set at least one image backend key:

- `NVIDIA_API_KEY` (preferred)
- `HUGGINGFACE_API_KEY` (fallback)

Optional:

- `IMAGE_BACKEND` = `nvidia` or `huggingface`
- `PROTOTYPE_DEMO_MODE` = `false` (template-based mockup) or `true` (AI mockup mode)
- `AUTO_HOODIE_ZONE` = `true`

## 2) Render (quickest)

This repo now includes `render.yaml`.

1. Push the repo to GitHub.
2. In Render, create a new Blueprint and select this repo.
3. Add the required env var(s) above in Render dashboard.
4. Deploy.

## 3) Generic Python Host

Use:

- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120`

## Notes

- Generated images/history are stored in local filesystem (`static/generated`, `data/history.json`).
- On hosts with ephemeral disks, data resets on restart/redeploy.
