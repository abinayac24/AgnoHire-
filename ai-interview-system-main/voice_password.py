from __future__ import annotations

import datetime
import hashlib
import io
import logging
import os
import tempfile
from pathlib import Path
import numpy as np
from pymongo.errors import DuplicateKeyError


logger = logging.getLogger(__name__)

VOICE_PASSWORD_THRESHOLD = float(os.getenv("VOICE_PASSWORD_THRESHOLD", "0.86"))
VOICE_PASSWORD_MIN_SECONDS = float(os.getenv("VOICE_PASSWORD_MIN_SECONDS", "0.75"))
VOICE_PASSWORD_MIN_RMS = float(os.getenv("VOICE_PASSWORD_MIN_RMS", "0.003"))
VOICE_FRAUD_WINDOW_SECONDS = float(os.getenv("VOICE_FRAUD_WINDOW_SECONDS", "1.2"))
VOICE_FRAUD_HOP_SECONDS = float(os.getenv("VOICE_FRAUD_HOP_SECONDS", "0.6"))
VOICE_MULTI_SPEAKER_SIMILARITY = float(
    os.getenv("VOICE_MULTI_SPEAKER_SIMILARITY", "0.76")
)
VOICE_MULTI_SPEAKER_MISMATCH_DELTA = float(
    os.getenv("VOICE_MULTI_SPEAKER_MISMATCH_DELTA", "0.12")
)
UPLOAD_DIR = Path(
    os.getenv("VOICE_PASSWORD_UPLOAD_DIR", "runtime_logs/voice_password_uploads")
)

_memory_profiles: dict[str, dict] = {}
_memory_logs: list[dict] = []


def hash_username(username: str) -> str:
    return hashlib.sha256(username.strip().lower().encode("utf-8")).hexdigest()


def init_voice_password_store(db) -> None:
    if db is None:
        logger.info(
            "[VoicePassword] MongoDB unavailable; using in-memory voice profile store"
        )
        return

    db.voice_profiles.create_index("username_hash", unique=True)
    db.voice_profiles.create_index("username")
    db.voice_auth_logs.create_index([("created_at", -1)])
    db.voice_auth_logs.create_index("username_hash")
    db.voice_verification_logs.create_index([("created_at", -1)])
    db.voice_verification_logs.create_index("session_id")
    db.voice_verification_logs.create_index("username_hash")
    logger.info("[VoicePassword] Voice profile collections ready")


def save_uploaded_voice_sample(file_storage) -> str:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    suffix = Path(file_storage.filename or "voice.wav").suffix.lower() or ".wav"
    if suffix not in {".wav", ".webm", ".ogg", ".mp3", ".m4a"}:
        suffix = ".wav"

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=UPLOAD_DIR)
    try:
        file_storage.save(tmp)
        return tmp.name
    finally:
        tmp.close()


def cleanup_file(path: str | None) -> None:
    if not path:
        return
    try:
        Path(path).unlink(missing_ok=True)
    except Exception:
        logger.debug("[VoicePassword] Could not remove temp file %s", path)


def _load_audio_signal(audio_path: str) -> tuple[np.ndarray, int]:
    import soundfile as sf
    from scipy import signal

    y, sr = sf.read(audio_path, dtype="float32", always_2d=False)
    if y.ndim > 1:
        y = y.mean(axis=1)
    if sr != 16000:
        gcd = np.gcd(int(sr), 16000)
        y = signal.resample_poly(y, 16000 // gcd, int(sr) // gcd).astype(np.float32)
        sr = 16000

    if y.size == 0:
        raise ValueError("The recording is empty. Please record your voice again.")

    y = _trim_silence(y, sr)
    return y.astype(np.float32), sr


def _extract_voice_embedding_from_signal(y: np.ndarray, sr: int) -> np.ndarray:
    from scipy import signal

    duration = float(len(y) / sr)
    if duration < VOICE_PASSWORD_MIN_SECONDS:
        raise ValueError("Recording is too short. Please speak for at least 3 seconds.")

    rms = float(np.sqrt(np.mean(np.square(y)))) if y.size else 0.0
    if rms < VOICE_PASSWORD_MIN_RMS:
        raise ValueError(
            "Voice is too quiet. Please speak clearly near the microphone."
        )

    y = y.astype(np.float32)
    y = y - float(np.mean(y))
    peak = float(np.max(np.abs(y))) if y.size else 0.0
    if peak > 0:
        y = y / peak

    frequencies, _, spectrum = signal.spectrogram(
        y,
        fs=sr,
        window="hann",
        nperseg=512,
        noverlap=256,
        scaling="spectrum",
        mode="magnitude",
    )
    spectrum = spectrum + 1e-8
    band_edges = np.linspace(80, min(7600, sr // 2), 33)
    band_energy = []
    for low, high in zip(band_edges[:-1], band_edges[1:]):
        mask = (frequencies >= low) & (frequencies < high)
        if np.any(mask):
            band_energy.append(np.log(spectrum[mask].mean(axis=0) + 1e-8))
        else:
            band_energy.append(np.zeros(spectrum.shape[1], dtype=np.float32))
    bands = np.vstack(band_energy)

    frame_energy = spectrum.sum(axis=0)
    centroid = (frequencies[:, None] * spectrum).sum(axis=0) / (frame_energy + 1e-8)
    bandwidth = np.sqrt(
        (((frequencies[:, None] - centroid) ** 2) * spectrum).sum(axis=0)
        / (frame_energy + 1e-8)
    )
    cumulative = np.cumsum(spectrum, axis=0)
    rolloff_index = np.argmax(cumulative >= (0.85 * frame_energy), axis=0)
    rolloff = frequencies[np.clip(rolloff_index, 0, len(frequencies) - 1)]

    frame_length = 512
    hop = 256
    zero_crossings = []
    for start in range(0, max(1, len(y) - frame_length), hop):
        frame = y[start : start + frame_length]
        if frame.size:
            zero_crossings.append(np.mean(np.abs(np.diff(np.signbit(frame)))))
    zcr = np.array(zero_crossings or [0.0], dtype=np.float32)

    band_mean = _standardize_vector(bands.mean(axis=1))
    band_std = _standardize_vector(bands.std(axis=1))
    band_low = _standardize_vector(np.percentile(bands, 25, axis=1))
    band_high = _standardize_vector(np.percentile(bands, 75, axis=1))
    dominant_bins = np.zeros(len(band_energy), dtype=np.float32)
    dominant_by_frame = np.argmax(bands, axis=0)
    for index in dominant_by_frame:
        dominant_bins[int(index)] += 1.0
    if dominant_bins.sum() > 0:
        dominant_bins = dominant_bins / dominant_bins.sum()
    dominant_bins = _standardize_vector(dominant_bins)

    scalar_features = np.array(
        [
            centroid.mean() / 8000.0,
            centroid.std() / 8000.0,
            bandwidth.mean() / 8000.0,
            bandwidth.std() / 8000.0,
            rolloff.mean() / 8000.0,
            rolloff.std() / 8000.0,
            zcr.mean(),
            zcr.std(),
        ],
        dtype=np.float32,
    )

    feature_parts = [
        band_mean,
        band_std,
        band_low,
        band_high,
        dominant_bins,
        scalar_features,
    ]
    embedding = np.concatenate(feature_parts).astype(np.float32)
    embedding = np.nan_to_num(embedding, nan=0.0, posinf=0.0, neginf=0.0)
    norm = np.linalg.norm(embedding)
    if norm > 0:
        embedding = embedding / norm
    return embedding.astype(np.float32)


def extract_voice_embedding(audio_path: str) -> np.ndarray:
    y, sr = _load_audio_signal(audio_path)
    return _extract_voice_embedding_from_signal(y, sr)


def _trim_silence(y: np.ndarray, sr: int) -> np.ndarray:
    frame = max(1, int(sr * 0.03))
    hop = max(1, int(sr * 0.015))
    if len(y) < frame:
        return y

    rms_values = []
    starts = []
    for start in range(0, len(y) - frame + 1, hop):
        chunk = y[start : start + frame]
        rms_values.append(float(np.sqrt(np.mean(np.square(chunk)))))
        starts.append(start)
    if not rms_values:
        return y

    rms_array = np.array(rms_values)
    threshold = max(
        VOICE_PASSWORD_MIN_RMS * 0.7, float(np.percentile(rms_array, 35)) * 1.4
    )
    active = np.where(rms_array >= threshold)[0]
    if active.size == 0:
        return y

    start = max(0, starts[int(active[0])] - frame)
    end = min(len(y), starts[int(active[-1])] + frame * 2)
    return y[start:end]


def _standardize_vector(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float32)
    std = float(np.std(values))
    if std <= 1e-8:
        return values - float(np.mean(values))
    return (values - float(np.mean(values))) / std


def average_embeddings(embeddings: list[np.ndarray]) -> np.ndarray:
    if not embeddings:
        raise ValueError("No valid voice recordings were provided.")
    stacked = np.stack([item.flatten().astype(np.float64) for item in embeddings])
    averaged = stacked.mean(axis=0)
    norm = np.linalg.norm(averaged)
    if norm > 0:
        averaged = averaged / norm
    return averaged.astype(np.float32)


def _embedding_to_bytes(embedding: np.ndarray) -> bytes:
    buffer = io.BytesIO()
    np.save(buffer, embedding.astype(np.float32))
    return buffer.getvalue()


def _bytes_to_embedding(data) -> np.ndarray:
    raw = data if isinstance(data, bytes) else bytes(data)
    return np.load(io.BytesIO(raw))


def voice_user_exists(db, username: str) -> bool:
    username_hash = hash_username(username)
    if db is None:
        return username_hash in _memory_profiles
    return (
        db.voice_profiles.find_one({"username_hash": username_hash}, {"_id": 1})
        is not None
    )


def get_voice_profile(db, username: str) -> dict | None:
    username = (username or "").strip()
    if not username:
        return None
    username_hash = hash_username(username)
    if db is None:
        profile = _memory_profiles.get(username_hash)
        return dict(profile) if profile else None
    profile = db.voice_profiles.find_one({"username_hash": username_hash}, {"_id": 0})
    return dict(profile) if profile else None


def save_voice_profile(
    db, username: str, email: str, embedding: np.ndarray, samples: int
) -> bool:
    username = username.strip()
    username_hash = hash_username(username)
    now = datetime.datetime.utcnow()

    profile = {
        "username_hash": username_hash,
        "username": username,
        "email": (email or "").strip().lower(),
        "embedding": _embedding_to_bytes(embedding),
        "embedding_dim": int(len(embedding.flatten())),
        "model_type": "local-mfcc-voice-password",
        "enrollment_samples": int(samples),
        "created_at": now,
        "updated_at": now,
    }

    if db is None:
        if username_hash in _memory_profiles:
            return False
        _memory_profiles[username_hash] = profile
        return True

    try:
        db.voice_profiles.insert_one(profile)
        return True
    except DuplicateKeyError:
        return False


def list_voice_profiles(db, username: str = "") -> list[dict]:
    projection = {
        "_id": 0,
        "username": 1,
        "username_hash": 1,
        "email": 1,
        "embedding": 1,
        "embedding_dim": 1,
        "model_type": 1,
    }
    if db is None:
        profiles = list(_memory_profiles.values())
        if username:
            username_hash = hash_username(username)
            profiles = [
                profile
                for profile in profiles
                if profile["username_hash"] == username_hash
            ]
        return [dict(profile) for profile in profiles]

    query = {"username_hash": hash_username(username)} if username else {}
    return list(db.voice_profiles.find(query, projection))


def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    a = vec_a.flatten().astype(np.float64)
    b = vec_b.flatten().astype(np.float64)
    if a.shape != b.shape:
        return 0.0
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.clip(np.dot(a, b) / (norm_a * norm_b), -1.0, 1.0))


def authenticate_voice_profile(
    db, probe_embedding: np.ndarray, username: str = ""
) -> dict:
    profiles = list_voice_profiles(db, username=username.strip())
    if not profiles:
        target = f" for '{username}'" if username else ""
        return {
            "authenticated": False,
            "username": "",
            "email": "",
            "score": 0.0,
            "threshold": VOICE_PASSWORD_THRESHOLD,
            "message": f"No voice profile found{target}. Please register first.",
        }

    best = None
    for profile in profiles:
        stored = _bytes_to_embedding(profile["embedding"])
        score = cosine_similarity(stored, probe_embedding)
        if best is None or score > best["score"]:
            best = {
                "username": profile.get("username", ""),
                "email": profile.get("email", ""),
                "score": round(score, 4),
                "threshold": VOICE_PASSWORD_THRESHOLD,
                "model": profile.get("model_type", "local-mfcc-voice-password"),
            }

    authenticated = bool(best and best["score"] >= VOICE_PASSWORD_THRESHOLD)
    best["authenticated"] = authenticated
    best["message"] = (
        "Voice password accepted."
        if authenticated
        else f"Voice password did not match. Best score: {round(best['score'] * 100)}%."
    )
    log_voice_auth_attempt(db, best["username"], authenticated, best["score"])
    return best


def log_voice_auth_attempt(db, username: str, success: bool, score: float) -> None:
    record = {
        "username_hash": hash_username(username) if username else "",
        "username": username,
        "success": bool(success),
        "score": float(score or 0),
        "threshold": VOICE_PASSWORD_THRESHOLD,
        "created_at": datetime.datetime.utcnow(),
    }
    if db is None:
        _memory_logs.append(record)
        return
    try:
        db.voice_auth_logs.insert_one(record)
    except Exception:
        logger.debug("[VoicePassword] Could not write auth log", exc_info=True)


def _windowed_embeddings(y: np.ndarray, sr: int) -> list[np.ndarray]:
    window = max(
        int(sr * VOICE_FRAUD_WINDOW_SECONDS), int(sr * VOICE_PASSWORD_MIN_SECONDS)
    )
    hop = max(1, int(sr * VOICE_FRAUD_HOP_SECONDS))
    embeddings: list[np.ndarray] = []
    if len(y) < window:
        try:
            embeddings.append(_extract_voice_embedding_from_signal(y, sr))
        except ValueError:
            return embeddings
        return embeddings

    for start in range(0, max(1, len(y) - window + 1), hop):
        chunk = y[start : start + window]
        if len(chunk) < int(sr * VOICE_PASSWORD_MIN_SECONDS):
            continue
        rms = float(np.sqrt(np.mean(np.square(chunk)))) if chunk.size else 0.0
        if rms < VOICE_PASSWORD_MIN_RMS * 0.9:
            continue
        try:
            embeddings.append(_extract_voice_embedding_from_signal(chunk, sr))
        except ValueError:
            continue
    return embeddings


def analyze_interview_voice(
    audio_path: str, enrolled_embedding: np.ndarray | None = None
) -> dict:
    y, sr = _load_audio_signal(audio_path)
    duration_seconds = round(float(len(y) / sr), 3)
    overall_embedding = _extract_voice_embedding_from_signal(y, sr)
    window_embeddings = _windowed_embeddings(y, sr)
    if not window_embeddings:
        window_embeddings = [overall_embedding]

    similarity_scores: list[float] = []
    score_spread = 0.0
    mean_similarity = 0.0
    min_similarity = 1.0
    max_similarity = 1.0
    mixed_voice_detected = False
    different_voice_detected = False

    if enrolled_embedding is not None:
        similarity_scores = [
            round(cosine_similarity(enrolled_embedding, emb), 4)
            for emb in window_embeddings
        ]
        mean_similarity = (
            float(np.mean(similarity_scores)) if similarity_scores else 0.0
        )
        min_similarity = min(similarity_scores) if similarity_scores else 0.0
        max_similarity = max(similarity_scores) if similarity_scores else 0.0
        score_spread = max_similarity - min_similarity
        different_voice_detected = (
            cosine_similarity(enrolled_embedding, overall_embedding)
            < VOICE_PASSWORD_THRESHOLD
        )
        strong_matches = sum(
            score >= VOICE_PASSWORD_THRESHOLD for score in similarity_scores
        )
        strong_mismatches = sum(
            score
            < max(0.0, VOICE_PASSWORD_THRESHOLD - VOICE_MULTI_SPEAKER_MISMATCH_DELTA)
            for score in similarity_scores
        )
        mixed_voice_detected = strong_matches > 0 and strong_mismatches > 0

    internal_similarities: list[float] = []
    if len(window_embeddings) >= 2:
        for idx in range(len(window_embeddings) - 1):
            internal_similarities.append(
                round(
                    cosine_similarity(
                        window_embeddings[idx], window_embeddings[idx + 1]
                    ),
                    4,
                )
            )

    internal_min = min(internal_similarities) if internal_similarities else 1.0
    internal_mean = (
        float(np.mean(internal_similarities)) if internal_similarities else 1.0
    )
    multiple_speakers_detected = bool(
        mixed_voice_detected
        or (
            len(window_embeddings) >= 2
            and internal_min < VOICE_MULTI_SPEAKER_SIMILARITY
            and (
                internal_mean < VOICE_MULTI_SPEAKER_SIMILARITY + 0.04
                or score_spread >= VOICE_MULTI_SPEAKER_MISMATCH_DELTA
            )
        )
    )

    reasons: list[str] = []
    if different_voice_detected:
        reasons.append("different_voice_detected")
    if mixed_voice_detected:
        reasons.append("mixed_voice_segments_detected")
    if multiple_speakers_detected:
        reasons.append("multiple_speakers_detected")

    return {
        "embedding": overall_embedding,
        "duration_seconds": duration_seconds,
        "segment_count": len(window_embeddings),
        "speaker_count_estimate": 2 if multiple_speakers_detected else 1,
        "similarity_scores": similarity_scores,
        "mean_similarity": round(mean_similarity, 4),
        "min_similarity": round(min_similarity, 4),
        "max_similarity": round(max_similarity, 4),
        "internal_min_similarity": round(float(internal_min), 4),
        "internal_mean_similarity": round(float(internal_mean), 4),
        "score_spread": round(float(score_spread), 4),
        "different_voice_detected": different_voice_detected,
        "mixed_voice_detected": mixed_voice_detected,
        "multiple_speakers_detected": multiple_speakers_detected,
        "reasons": reasons,
    }


def log_voice_verification(
    db,
    *,
    username: str,
    session_id: str,
    question_number: str,
    source: str,
    authenticated: bool,
    score: float,
    threshold: float,
    multiple_speakers_detected: bool,
    different_voice_detected: bool,
    speaker_count_estimate: int,
    reasons: list[str] | None = None,
) -> None:
    record = {
        "username_hash": hash_username(username) if username else "",
        "username": username,
        "session_id": (session_id or "").strip(),
        "question_number": str(question_number or "").strip(),
        "source": (source or "").strip(),
        "authenticated": bool(authenticated),
        "score": float(score or 0.0),
        "threshold": float(threshold or VOICE_PASSWORD_THRESHOLD),
        "multiple_speakers_detected": bool(multiple_speakers_detected),
        "different_voice_detected": bool(different_voice_detected),
        "speaker_count_estimate": int(max(1, speaker_count_estimate or 1)),
        "reasons": list(reasons or []),
        "created_at": datetime.datetime.utcnow(),
    }
    if db is None:
        _memory_logs.append(record)
        return
    try:
        db.voice_verification_logs.insert_one(record)
    except Exception:
        logger.debug("[VoicePassword] Could not write verification log", exc_info=True)


# =========================
# ADMIN VOICE PROFILE MANAGEMENT
# =========================

def list_all_voice_profiles(db, search: str = "", limit: int = 200) -> list[dict]:
    """List all voice profiles with optional search filter."""
    search_text = (search or "").strip().lower()
    max_items = max(1, min(limit, 1000))

    projection = {
        "_id": 0,
        "username": 1,
        "username_hash": 1,
        "email": 1,
        "embedding_dim": 1,
        "model_type": 1,
        "enrollment_samples": 1,
        "created_at": 1,
        "updated_at": 1,
    }

    if db is None:
        profiles = list(_memory_profiles.values())
        if search_text:
            profiles = [
                p for p in profiles
                if search_text in p.get("username", "").lower()
                or search_text in p.get("email", "").lower()
            ]
        # Sort by created_at descending
        profiles = sorted(profiles, key=lambda x: x.get("created_at", datetime.datetime.min), reverse=True)
        return [dict(p) for p in profiles[:max_items]]

    query = {}
    if search_text:
        query = {
            "$or": [
                {"username": {"$regex": search_text, "$options": "i"}},
                {"email": {"$regex": search_text, "$options": "i"}},
            ]
        }

    return list(
        db.voice_profiles
        .find(query, projection)
        .sort("created_at", -1)
        .limit(max_items)
    )


def get_voice_profile_with_auth_logs(db, username: str) -> dict | None:
    """Get voice profile with authentication history."""
    profile = get_voice_profile(db, username)
    if not profile:
        return None

    username_hash = hash_username(username)

    # Get recent auth logs
    if db is None:
        auth_logs = [
            log for log in _memory_logs
            if log.get("username_hash") == username_hash and log.get("success")
        ]
        auth_logs = sorted(auth_logs, key=lambda x: x.get("created_at", datetime.datetime.min), reverse=True)[:20]
    else:
        auth_logs = list(
            db.voice_auth_logs
            .find({"username_hash": username_hash}, {"_id": 0})
            .sort("created_at", -1)
            .limit(20)
        )

    # Get verification logs from interview sessions
    verification_logs = []
    if db is not None:
        verification_logs = list(
            db.voice_verification_logs
            .find({"username_hash": username_hash}, {"_id": 0})
            .sort("created_at", -1)
            .limit(50)
        )

    # Calculate stats
    total_attempts = len(auth_logs)
    successful_attempts = sum(1 for log in auth_logs if log.get("success"))
    last_login = auth_logs[0].get("created_at") if auth_logs else None

    return {
        "profile": profile,
        "auth_logs": auth_logs,
        "verification_logs": verification_logs,
        "stats": {
            "total_attempts": total_attempts,
            "successful_attempts": successful_attempts,
            "last_login": last_login,
        }
    }


def update_voice_profile_metadata(db, username: str, updates: dict) -> bool:
    """Update voice profile metadata (email, etc.)."""
    username = (username or "").strip()
    if not username:
        return False

    username_hash = hash_username(username)
    now = datetime.datetime.utcnow()

    allowed_fields = {"email"}
    update_data = {k: v for k, v in updates.items() if k in allowed_fields}
    if not update_data:
        return False

    update_data["updated_at"] = now

    if db is None:
        if username_hash not in _memory_profiles:
            return False
        _memory_profiles[username_hash].update(update_data)
        return True

    result = db.voice_profiles.update_one(
        {"username_hash": username_hash},
        {"$set": update_data}
    )
    return result.modified_count > 0


def delete_voice_profile(db, username: str) -> dict:
    """Delete voice profile and related logs."""
    username = (username or "").strip()
    if not username:
        return {"deleted": False, "reason": "username_required"}

    username_hash = hash_username(username)

    if db is None:
        if username_hash not in _memory_profiles:
            return {"deleted": False, "reason": "profile_not_found"}
        del _memory_profiles[username_hash]
        # Remove related logs from memory
        global _memory_logs
        _memory_logs = [log for log in _memory_logs if log.get("username_hash") != username_hash]
        return {"deleted": True, "username": username}

    # Delete profile
    profile_result = db.voice_profiles.delete_one({"username_hash": username_hash})

    # Delete auth logs
    auth_logs_deleted = db.voice_auth_logs.delete_many({"username_hash": username_hash}).deleted_count

    # Delete verification logs
    verification_logs_deleted = db.voice_verification_logs.delete_many({"username_hash": username_hash}).deleted_count

    return {
        "deleted": profile_result.deleted_count > 0,
        "username": username,
        "auth_logs_deleted": auth_logs_deleted,
        "verification_logs_deleted": verification_logs_deleted,
    }


def reset_voice_profile_for_reregistration(db, username: str) -> dict:
    """Reset voice profile to allow re-registration."""
    username = (username or "").strip()
    if not username:
        return {"reset": False, "reason": "username_required"}

    username_hash = hash_username(username)

    if db is None:
        if username_hash in _memory_profiles:
            del _memory_profiles[username_hash]
        return {"reset": True, "username": username}

    result = db.voice_profiles.delete_one({"username_hash": username_hash})
    return {
        "reset": result.deleted_count > 0,
        "username": username,
        "deleted_count": result.deleted_count,
    }


def get_voice_profile_stats(db) -> dict:
    """Get overall voice profile statistics for admin dashboard."""
    if db is None:
        total_profiles = len(_memory_profiles)
        recent_registrations = len([
            p for p in _memory_profiles.values()
            if p.get("created_at", datetime.datetime.min) > datetime.datetime.utcnow() - datetime.timedelta(days=7)
        ])
        return {
            "total_profiles": total_profiles,
            "recent_registrations": recent_registrations,
            "total_auth_attempts": len(_memory_logs),
        }

    total_profiles = db.voice_profiles.count_documents({})
    recent_registrations = db.voice_profiles.count_documents({
        "created_at": {"$gte": datetime.datetime.utcnow() - datetime.timedelta(days=7)}
    })
    total_auth_attempts = db.voice_auth_logs.count_documents({})
    successful_auths = db.voice_auth_logs.count_documents({"success": True})

    return {
        "total_profiles": total_profiles,
        "recent_registrations": recent_registrations,
        "total_auth_attempts": total_auth_attempts,
        "successful_auths": successful_auths,
        "failed_auths": total_auth_attempts - successful_auths,
    }
