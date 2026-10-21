"""Validate private timetable uploads; never use the supplied file name."""
import io
import json
import os
import secrets
from pathlib import Path
from PIL import Image
from .. import config

Image.MAX_IMAGE_PIXELS = 16000000


def save_upload(raw, mime):
    if not raw or len(raw) > 10 * 1024 * 1024:
        raise ValueError('请选择不超过 10 MB 的截图或 PDF')
    key = secrets.token_hex(16)
    folder = config.UPLOAD_DIR / key
    folder.mkdir(parents=True, mode=0o700)
    try:
        text = ''
        images = []
        if raw.startswith(b'%PDF'):
            import pymupdf
            with pymupdf.open(stream=raw, filetype='pdf') as doc:
                if doc.is_encrypted or not 1 <= len(doc) <= 6:
                    raise ValueError('PDF 必须未加密且不超过 6 页')
                for index, page in enumerate(doc):
                    text += page.get_text()[:20000] + '\n'
                    # Bound pixel allocation, even for very large page dimensions.
                    scale = min(2, 1800 / max(page.rect.width, page.rect.height))
                    pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale))
                    path = folder / f'{index}.png'
                    pix.save(path)
                    images.append(path.name)
        else:
            with Image.open(io.BytesIO(raw)) as image:
                image.load()
                image.thumbnail((2000, 2000))
                image.convert('RGB').save(folder / '0.png')
                images.append('0.png')
        (folder / 'manifest.json').write_text(json.dumps({'text': text[:60000], 'images': images}), encoding='utf-8')
        for path in folder.iterdir():
            os.chmod(path, 0o600)
        return key
    except Exception as exc:
        import shutil
        shutil.rmtree(folder)
        if isinstance(exc, ValueError):
            raise
        raise ValueError('文件无法读取，请上传有效的 PNG、JPEG 或未加密 PDF') from exc


def load_upload(key):
    if len(key) != 32 or any(c not in '0123456789abcdef' for c in key):
        raise ValueError('文件标识无效')
    import base64
    folder = config.UPLOAD_DIR / key
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    return manifest['text'], ['data:image/png;base64,' + base64.b64encode((folder / name).read_bytes()).decode() for name in manifest['images']]
