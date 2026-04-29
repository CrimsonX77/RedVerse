"""
waifu.com API server — FastAPI app with auth, user-scoped data, CORS, static serving.
Run: uvicorn server:app --port 8800 --reload
"""

import os
import re
import sys
import uuid
from typing import Optional

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from auth import require_auth, router as auth_router
from config import API_PORT, CORS_ORIGINS, USER_DATA_DIR
from db import get_db, init_db
from models import (
    ChatMessage,
    EDriveState,
    GalleryItem,
    Payment,
    Preference,
    SoulSchema,
    User,
)

app = FastAPI(title="waifu.com API", version="1.0.0")

# ── CORS ──────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Auth routes ───────────────────────────────────────────────────────────────

app.include_router(auth_router)

# ── Startup ───────────────────────────────────────────────────────────────────

@app.on_event("startup")
def on_startup():
    init_db()
    os.makedirs(USER_DATA_DIR, exist_ok=True)


# ── Pydantic models for data endpoints ───────────────────────────────────────

class ChatMessageIn(BaseModel):
    role: str
    content: str
    model_used: Optional[str] = None

class EDriveIn(BaseModel):
    emotion_data: dict

class SoulSchemaIn(BaseModel):
    name: str
    yaml_content: str

class PrefsIn(BaseModel):
    prefs: dict  # { key: value, ... }

class PaymentIn(BaseModel):
    product: str
    amount: float
    currency: str = "USD"
    stripe_session_id: Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE 2: User-Scoped Data API
# ══════════════════════════════════════════════════════════════════════════════

# ── Chat History ──────────────────────────────────────────────────────────────

VALID_ROOMS = {"chat", "oracle", "luna"}

@app.get("/api/user/chat/{room}")
def get_chat(
    room: str,
    limit: int = Query(50, ge=1, le=500),
    user: User = Depends(require_auth),
    db: DBSession = Depends(get_db),
):
    if room not in VALID_ROOMS:
        raise HTTPException(400, "Invalid room")
    msgs = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == user.id, ChatMessage.room == room)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {"id": m.id, "role": m.role, "content": m.content, "model_used": m.model_used, "created_at": str(m.created_at)}
        for m in reversed(msgs)
    ]


@app.post("/api/user/chat/{room}")
def post_chat(
    room: str,
    body: ChatMessageIn,
    user: User = Depends(require_auth),
    db: DBSession = Depends(get_db),
):
    if room not in VALID_ROOMS:
        raise HTTPException(400, "Invalid room")
    msg = ChatMessage(
        user_id=user.id,
        room=room,
        role=body.role,
        content=body.content,
        model_used=body.model_used,
    )
    db.add(msg)
    db.commit()
    return {"id": msg.id, "ok": True}


@app.delete("/api/user/chat/{room}")
def delete_chat(
    room: str,
    user: User = Depends(require_auth),
    db: DBSession = Depends(get_db),
):
    if room not in VALID_ROOMS:
        raise HTTPException(400, "Invalid room")
    db.query(ChatMessage).filter(
        ChatMessage.user_id == user.id, ChatMessage.room == room
    ).delete()
    db.commit()
    return {"ok": True}


# ── E-Drive ───────────────────────────────────────────────────────────────────

@app.get("/api/user/edrive")
def get_edrive(user: User = Depends(require_auth), db: DBSession = Depends(get_db)):
    state = db.query(EDriveState).filter(EDriveState.user_id == user.id).first()
    if state is None:
        return {"emotion_data": {}}
    return {"emotion_data": state.emotion_data}


@app.put("/api/user/edrive")
def put_edrive(
    body: EDriveIn,
    user: User = Depends(require_auth),
    db: DBSession = Depends(get_db),
):
    state = db.query(EDriveState).filter(EDriveState.user_id == user.id).first()
    if state is None:
        state = EDriveState(user_id=user.id, emotion_data=body.emotion_data)
        db.add(state)
    else:
        state.emotion_data = body.emotion_data
    db.commit()
    return {"ok": True}


# ── Gallery ───────────────────────────────────────────────────────────────────

_SAFE_FILENAME = re.compile(r"^[\w\-. ]+$")

@app.get("/api/user/gallery")
def get_gallery(
    source: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user: User = Depends(require_auth),
    db: DBSession = Depends(get_db),
):
    q = db.query(GalleryItem).filter(GalleryItem.user_id == user.id)
    if source:
        q = q.filter(GalleryItem.source == source)
    items = (
        q.order_by(GalleryItem.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return [
        {
            "id": i.id,
            "source": i.source,
            "filename": i.filename,
            "prompt": i.prompt,
            "metadata": i.metadata_,
            "created_at": str(i.created_at),
            "url": f"/api/user/gallery/{i.id}/file",
        }
        for i in items
    ]


@app.post("/api/user/gallery")
async def upload_gallery(
    source: str = Query(...),
    prompt: Optional[str] = Query(None),
    file: UploadFile = File(...),
    user: User = Depends(require_auth),
    db: DBSession = Depends(get_db),
):
    # Sanitize filename
    safe_name = re.sub(r"[^\w\-. ]", "_", file.filename or "image.png")
    unique_name = f"{uuid.uuid4().hex[:8]}_{safe_name}"

    # User-scoped directory — prevents cross-user access
    user_gallery_dir = os.path.join(USER_DATA_DIR, user.id, "gallery")
    os.makedirs(user_gallery_dir, exist_ok=True)
    blob_path = os.path.join(user_gallery_dir, unique_name)

    # Write file (limit 20 MB)
    content = await file.read(20 * 1024 * 1024 + 1)
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(413, "File too large (max 20 MB)")
    with open(blob_path, "wb") as f:
        f.write(content)

    item = GalleryItem(
        user_id=user.id,
        source=source,
        filename=unique_name,
        blob_path=blob_path,
        prompt=prompt,
    )
    db.add(item)
    db.commit()
    return {"id": item.id, "filename": unique_name, "ok": True}


@app.delete("/api/user/gallery/{item_id}")
def delete_gallery_item(
    item_id: str,
    user: User = Depends(require_auth),
    db: DBSession = Depends(get_db),
):
    item = db.query(GalleryItem).filter(
        GalleryItem.id == item_id, GalleryItem.user_id == user.id
    ).first()
    if item is None:
        raise HTTPException(404, "Not found")
    # Remove file from disk
    if os.path.exists(item.blob_path):
        os.remove(item.blob_path)
    db.delete(item)
    db.commit()
    return {"ok": True}


@app.get("/api/user/gallery/{item_id}/file")
def get_gallery_file(
    item_id: str,
    user: User = Depends(require_auth),
    db: DBSession = Depends(get_db),
):
    item = db.query(GalleryItem).filter(
        GalleryItem.id == item_id, GalleryItem.user_id == user.id
    ).first()
    if item is None:
        raise HTTPException(404, "Not found")
    if not os.path.exists(item.blob_path):
        raise HTTPException(404, "File missing")

    from fastapi.responses import FileResponse
    return FileResponse(item.blob_path)


# ── Soul Schemas ──────────────────────────────────────────────────────────────

@app.get("/api/user/schemas")
def get_schemas(user: User = Depends(require_auth), db: DBSession = Depends(get_db)):
    schemas = db.query(SoulSchema).filter(SoulSchema.user_id == user.id).all()
    return [
        {"id": s.id, "name": s.name, "is_active": s.is_active, "created_at": str(s.created_at)}
        for s in schemas
    ]


@app.post("/api/user/schemas")
def create_schema(
    body: SoulSchemaIn,
    user: User = Depends(require_auth),
    db: DBSession = Depends(get_db),
):
    schema = SoulSchema(user_id=user.id, name=body.name, yaml_content=body.yaml_content)
    db.add(schema)
    db.commit()
    return {"id": schema.id, "ok": True}


@app.put("/api/user/schemas/{schema_id}")
def update_schema(
    schema_id: str,
    body: SoulSchemaIn,
    user: User = Depends(require_auth),
    db: DBSession = Depends(get_db),
):
    schema = db.query(SoulSchema).filter(
        SoulSchema.id == schema_id, SoulSchema.user_id == user.id
    ).first()
    if schema is None:
        raise HTTPException(404, "Not found")
    schema.name = body.name
    schema.yaml_content = body.yaml_content
    db.commit()
    return {"ok": True}


@app.delete("/api/user/schemas/{schema_id}")
def delete_schema(
    schema_id: str,
    user: User = Depends(require_auth),
    db: DBSession = Depends(get_db),
):
    schema = db.query(SoulSchema).filter(
        SoulSchema.id == schema_id, SoulSchema.user_id == user.id
    ).first()
    if schema is None:
        raise HTTPException(404, "Not found")
    db.delete(schema)
    db.commit()
    return {"ok": True}


@app.put("/api/user/schemas/{schema_id}/activate")
def activate_schema(
    schema_id: str,
    user: User = Depends(require_auth),
    db: DBSession = Depends(get_db),
):
    # Deactivate all, then activate the target
    db.query(SoulSchema).filter(SoulSchema.user_id == user.id).update({"is_active": False})
    schema = db.query(SoulSchema).filter(
        SoulSchema.id == schema_id, SoulSchema.user_id == user.id
    ).first()
    if schema is None:
        raise HTTPException(404, "Not found")
    schema.is_active = True
    db.commit()
    return {"ok": True}


# ── Preferences ───────────────────────────────────────────────────────────────

@app.get("/api/user/prefs")
def get_prefs(user: User = Depends(require_auth), db: DBSession = Depends(get_db)):
    prefs = db.query(Preference).filter(Preference.user_id == user.id).all()
    return {p.key: p.value for p in prefs}


@app.put("/api/user/prefs")
def put_prefs(
    body: PrefsIn,
    user: User = Depends(require_auth),
    db: DBSession = Depends(get_db),
):
    for key, value in body.prefs.items():
        existing = (
            db.query(Preference)
            .filter(Preference.user_id == user.id, Preference.key == key)
            .first()
        )
        if existing:
            existing.value = str(value) if value is not None else None
        else:
            db.add(Preference(user_id=user.id, key=key, value=str(value) if value is not None else None))
    db.commit()
    return {"ok": True}


# ── Payments ──────────────────────────────────────────────────────────────────

@app.post("/api/user/payment/record")
def record_payment(
    body: PaymentIn,
    user: User = Depends(require_auth),
    db: DBSession = Depends(get_db),
):
    payment = Payment(
        user_id=user.id,
        product=body.product,
        amount=body.amount,
        currency=body.currency,
        stripe_session_id=body.stripe_session_id,
    )
    db.add(payment)
    db.commit()
    return {"id": payment.id, "ok": True}


@app.get("/api/user/payment/status")
def payment_status(user: User = Depends(require_auth), db: DBSession = Depends(get_db)):
    payments = db.query(Payment).filter(Payment.user_id == user.id).all()
    return {
        "access_tier": user.access_tier,
        "tier_name": user.tier_name,
        "payments": [
            {"product": p.product, "amount": p.amount, "currency": p.currency, "paid_at": str(p.paid_at)}
            for p in payments
        ],
    }


# ── Music list endpoint ───────────────────────────────────────────────────────

MUSIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "music")


@app.get("/api/music/list")
def list_music():
    """Return sorted list of music file paths for the player widget."""
    from urllib.parse import quote
    if not os.path.isdir(MUSIC_DIR):
        return {"files": []}
    files = sorted(
        f"/assets/music/{quote(f)}" for f in os.listdir(MUSIC_DIR) if f.lower().endswith((".mp3", ".ogg", ".wav", ".flac"))
    )
    return {"files": files}


# ── Static file serving ───────────────────────────────────────────────────────
# Mount /assets/ BEFORE the catch-all "/" so HTML refs like ../assets/images/... resolve
ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")
if os.path.isdir(ASSETS_DIR):
    app.mount("/assets", StaticFiles(directory=ASSETS_DIR, follow_symlink=True), name="assets")

HTML_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "html")
if os.path.isdir(HTML_DIR):
    app.mount("/", StaticFiles(directory=HTML_DIR, html=True, follow_symlink=True), name="static")


# ── Direct launch support (used by redversemasterlauncher.py) ────────────────

if __name__ == "__main__":
    import uvicorn
    port = int(sys.argv[1]) if len(sys.argv) > 1 else API_PORT
    uvicorn.run(app, host="127.0.0.1", port=port)
    app.include_router(router)
