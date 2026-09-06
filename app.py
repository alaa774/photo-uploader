import os
import io

from flask import Flask, request, jsonify, redirect, session
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload


app = Flask(__name__)

# Secret used to securely keep OAuth data between Google authorization
# and the callback request.
app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY",
    "photo-uploader-secret"
)

SCOPES = [
    "https://www.googleapis.com/auth/drive.file"
]

REDIRECT_URI = os.environ.get(
    "GOOGLE_REDIRECT_URI",
    ""
).strip()

CLIENT_ID = os.environ.get(
    "GOOGLE_CLIENT_ID",
    ""
).strip()

CLIENT_SECRET = os.environ.get(
    "GOOGLE_CLIENT_SECRET",
    ""
).strip()

TOKEN_FILE = "token.json"


def oauth_flow():
    if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
        raise RuntimeError(
            "Set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET and GOOGLE_REDIRECT_URI"
        )

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

    try:
        creds = Credentials.from_authorized_user_file(
            TOKEN_FILE,
            SCOPES
        )

        if not creds.valid:
            if creds.expired and creds.refresh_token:
                from google.auth.transport.requests import Request

                creds.refresh(Request())

                with open(TOKEN_FILE, "w", encoding="utf-8") as f:
                    f.write(creds.to_json())
            else:
                return None

        return build(
            "drive",
            "v3",
            credentials=creds
        )

    except Exception:
        return None


@app.get("/")
def home():
    return jsonify({
        "ok": True,
        "service": "photo-uploader",
        "message": "Backend is running"
    })


@app.get("/health")
def health():
    return jsonify({
        "ok": True
    })


@app.get("/auth/google")
def auth_google():
    flow = oauth_flow()

    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )

    # IMPORTANT:
    # Save both state and PKCE code verifier.
    # They are required when Google redirects back to /oauth2callback.
    session["oauth_state"] = state
    session["oauth_code_verifier"] = flow.code_verifier

    return redirect(authorization_url)


@app.get("/oauth2callback")
def oauth2callback():
    # Check OAuth state first.
    saved_state = session.pop("oauth_state", None)
    returned_state = request.args.get("state")

    if not saved_state or not returned_state:
        return "OAuth state is missing.", 400

    if saved_state != returned_state:
        return "Invalid OAuth state.", 400

    # Create the OAuth flow again.
    flow = oauth_flow()

    # IMPORTANT:
    # Restore the PKCE verifier generated before redirecting to Google.
    code_verifier = session.pop("oauth_code_verifier", None)

    if not code_verifier:
        return "OAuth code verifier is missing.", 400

    flow.code_verifier = code_verifier

    try:
        flow.fetch_token(
            authorization_response=request.url
        )

    except Exception as e:
        print("OAuth callback error:", repr(e))
        return (
            "حدث خطأ أثناء ربط Google Drive. "
            "راجع Logs في Render."
        ), 500

    # Save Google's authorization token.
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        f.write(flow.credentials.to_json())

    return """
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>تم الربط</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                text-align: center;
                padding: 50px 20px;
            }

            .success {
                font-size: 24px;
                margin-top: 30px;
            }
        </style>
    </head>
    <body>
        <div class="success">
            تم ربط Google Drive بنجاح ✅
        </div>
    </body>
    </html>
    """


@app.post("/upload")
def upload():
    if "file" not in request.files:
        return jsonify({
            "ok": False,
            "error": "No file field"
        }), 400

    file = request.files["file"]

    if not file.filename:
        return jsonify({
            "ok": False,
            "error": "Empty filename"
        }), 400

    service = get_drive_service()

    if service is None:
        return jsonify({
            "ok": False,
            "error": "Google Drive is not connected",
            "auth_url": "/auth/google"
        }), 401

    # Optional Google Drive folder ID.
    folder_id = os.environ.get(
        "GOOGLE_DRIVE_FOLDER_ID",
        ""
    ).strip()

    metadata = {
        "name": file.filename
    }

    if folder_id:
        metadata["parents"] = [folder_id]

    file_data = file.read()

    media = MediaIoBaseUpload(
        io.BytesIO(file_data),
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
    port = int(
        os.environ.get("PORT", "10000")
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
