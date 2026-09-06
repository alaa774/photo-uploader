import os
import io
from flask import Flask, request, jsonify, redirect
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

app = Flask(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI", "").strip()
CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()

# For the first setup/testing run, the OAuth token is kept in token.json.
# Do NOT put Google client secrets or tokens in GitHub.
TOKEN_FILE = "token.json"

def oauth_flow():
    if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
        raise RuntimeError("Set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET and GOOGLE_REDIRECT_URI")
    client_config = {
        "web": {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [REDIRECT_URI],
        }
    }
    return Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )

def get_drive_service():
    from google.oauth2.credentials import Credentials

    if not os.path.exists(TOKEN_FILE):
        return None

    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
            with open(TOKEN_FILE, "w", encoding="utf-8") as f:
                f.write(creds.to_json())
        else:
            return None
    return build("drive", "v3", credentials=creds)

@app.get("/")
def home():
    return jsonify({
        "ok": True,
        "service": "photo-uploader",
        "message": "Backend is running"
    })

@app.get("/health")
def health():
    return jsonify({"ok": True})

@app.get("/auth/google")
def auth_google():
    flow = oauth_flow()
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    # State is included in the OAuth URL; for this simple setup we do not
    # store it server-side. This endpoint is intended for the owner's setup.
    return redirect(authorization_url)

@app.get("/oauth2callback")
def oauth2callback():
    flow = oauth_flow()
    flow.fetch_token(authorization_response=request.url)
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        f.write(flow.credentials.to_json())
    return "تم ربط Google Drive بنجاح. يمكنك الآن استخدام التطبيق."

@app.post("/upload")
def upload():
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "No file field"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"ok": False, "error": "Empty filename"}), 400

    service = get_drive_service()
    if service is None:
        return jsonify({
            "ok": False,
            "error": "Google Drive is not connected",
            "auth_url": "/auth/google"
        }), 401

    # Optional folder ID. If empty, files are uploaded to Drive root.
    folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "").strip()

    metadata = {"name": file.filename}
    if folder_id:
        metadata["parents"] = [folder_id]

    media = MediaIoBaseUpload(
        io.BytesIO(file.read()),
        mimetype=file.mimetype or "application/octet-stream",
        resumable=False,
    )

    created = service.files().create(
        body=metadata,
        media_body=media,
        fields="id,name",
    ).execute()

    return jsonify({
        "ok": True,
        "id": created.get("id"),
        "name": created.get("name"),
        "message": "تم رفع الملف بنجاح"
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
