# photo-uploader backend

Backend Flask for uploading photos to Google Drive through Google OAuth.

## Render
Build Command:
pip install -r requirements.txt

Start Command:
gunicorn app:app

## Environment variables
GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET
GOOGLE_REDIRECT_URI
GOOGLE_DRIVE_FOLDER_ID (optional)

Never commit Google client secrets or token.json to GitHub.
