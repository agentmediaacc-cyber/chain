import os
from pathlib import Path
from PIL import Image
from werkzeug.utils import secure_filename

IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
AUDIO_EXTENSIONS = {"mp3", "wav", "m4a"}
VIDEO_EXTENSIONS = {"mp4", "mov", "webm"}


def allowed_file(filename, allowed):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in allowed


def save_uploaded_file(file, folder, prefix="upload"):
    if not file or not file.filename:
        return None

    Path(folder).mkdir(parents=True, exist_ok=True)
    filename = secure_filename(file.filename)
    final_name = f"{prefix}_{filename}"
    path = os.path.join(folder, final_name)
    file.save(path)
    return "/" + path


def compress_image(path, max_size=(1400, 1400), quality=82):
    real_path = path.lstrip("/")
    if not os.path.exists(real_path):
        return path

    try:
        img = Image.open(real_path)
        img.thumbnail(max_size)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(real_path, optimize=True, quality=quality)
    except Exception as exc:
        print("[MEDIA ENGINE] image compression skipped:", exc)

    return path
