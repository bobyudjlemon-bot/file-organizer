"""Offline OCR: bounded input, disposable working copies, exclusive outputs."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageOps
from pypdf import PdfReader

MODEL_DIR = Path(__file__).resolve().parents[1] / '.ocr' / 'tessdata'
LANGUAGES = 'chi_sim+chi_tra+eng'
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff', '.webp'}
MAX_PIXELS = 25_000_000
MAX_PAGES = 20


def check_runtime():
    if not shutil.which('tesseract'):
        raise ValueError('缺少Tesseract，请运行安装步骤')
    for lang in LANGUAGES.split('+'):
        if not (MODEL_DIR / f'{lang}.traineddata').is_file():
            raise ValueError('缺少OCR语言包，请运行 scripts/setup_ocr.py')


def image_text(image):
    import pytesseract
    check_runtime()
    if image.width * image.height > MAX_PIXELS:
        raise ValueError('图片超过2500万像素，跳过OCR')
    normalized = ImageOps.exif_transpose(image).convert('RGB')
    try:
        text = pytesseract.image_to_string(
            normalized, lang=LANGUAGES,
            config=f'--tessdata-dir "{MODEL_DIR}" --psm 6', timeout=45,
        )
    finally:
        normalized.close()
    if not text.strip():
        raise ValueError('OCR未识别出文字，请人工核对')
    return text


def extract_ocr(path):
    """Read raster images or textless PDF pages; do not write beside source."""
    path = Path(path)
    if path.stat().st_size > 30 * 1024**2:
        raise ValueError('OCR文件超过30MB')
    if path.suffix.lower() in IMAGE_EXTENSIONS:
        with Image.open(path) as image:
            if getattr(image, 'n_frames', 1) != 1:
                raise ValueError('多帧图片不自动OCR，请拆页后处理')
            return image_text(image)
    if path.suffix.lower() != '.pdf':
        raise ValueError('OCR仅支持PDF和常见单帧位图')
    reader = PdfReader(path)
    if reader.is_encrypted:
        raise ValueError('不处理加密PDF')
    if len(reader.pages) > MAX_PAGES:
        raise ValueError('OCR模式最多20页，请拆分后处理')
    import pypdfium2 as pdfium
    chunks = []
    with pdfium.PdfDocument(path) as pdf:
        for index, page in enumerate(reader.pages):
            text = page.extract_text() or ''
            if not text.strip():
                rendered_page = pdf[index]
                bitmap = None
                image = None
                try:
                    width, height = rendered_page.get_size()
                    scale = 200 / 72
                    if width * height * scale**2 > MAX_PIXELS:
                        raise ValueError('PDF页面渲染超过2500万像素')
                    bitmap = rendered_page.render(scale=scale)
                    image = bitmap.to_pil()
                    text = image_text(image)
                finally:
                    if image is not None:
                        image.close()
                    if bitmap is not None:
                        bitmap.close()
                    rendered_page.close()
            chunks.append(text)
            if sum(map(len, chunks)) > 200_000:
                raise ValueError('OCR文本超过20万字符')
    return '\n'.join(chunks)


def searchable_pdf(source, output, confirmed=False):
    """Generate a derivative PDF only after explicit confirmation."""
    from .core import digest, regular_open, save_json
    if not confirmed:
        raise ValueError('需确认生成OCR衍生副本后使用--confirm')
    source = Path(source)
    if source.is_symlink():
        raise ValueError('不处理符号链接')
    source = source.resolve()
    output = Path(output).resolve()
    if source.is_relative_to(output):
        raise ValueError('输出目录不能包含原件')
    if source.suffix.lower() != '.pdf' or source.stat().st_size > 30 * 1024**2:
        raise ValueError('仅处理30MB以内的PDF')
    check_runtime()
    reader = PdfReader(source)
    if reader.is_encrypted or len(reader.pages) > MAX_PAGES:
        raise ValueError('不处理加密或超过20页的PDF')
    # Bound page rendering before invoking an external parser.
    for page in reader.pages:
        if float(page.mediabox.width) * float(page.mediabox.height) * (300 / 72)**2 > MAX_PIXELS:
            raise ValueError('PDF页面过大，请缩小后处理')
    checksum = digest(source)
    output.mkdir(parents=True, exist_ok=False)
    try:
        with tempfile.TemporaryDirectory(prefix='organizer-ocr-') as temp:
            work = Path(temp)
            with regular_open(source) as read, (work / 'input.pdf').open('xb') as write:
                shutil.copyfileobj(read, write)
            if digest(work / 'input.pdf') != checksum:
                raise ValueError('读取期间原件变化，请重试')
            env = os.environ.copy()
            env['TESSDATA_PREFIX'] = str(MODEL_DIR)
            env['OMP_THREAD_LIMIT'] = '2'
            result = subprocess.run(
                [sys.executable, '-m', 'ocrmypdf', '--skip-text', '--output-type', 'pdf', '--rasterizer', 'pypdfium',
                 '--optimize', '0', '--jobs', '2', '--tesseract-timeout', '45',
                 '--max-image-mpixels', '25', '--skip-big', '25',
                 '-l', LANGUAGES, str(work / 'input.pdf'), str(work / 'searchable.pdf')],
                capture_output=True, text=True, timeout=300, env=env,
            )
            (output / 'ocr.log').write_text(result.stdout + result.stderr, encoding='utf-8')
            if result.returncode:
                raise ValueError(f'OCRmyPDF失败，退出码{result.returncode}；详见ocr.log')
            converted = PdfReader(work / 'searchable.pdf')
            if len(converted.pages) != len(reader.pages):
                raise ValueError('OCR输出页数不一致')
            page_texts = [(page.extract_text() or '').strip() for page in converted.pages]
            if not any(page_texts):
                raise ValueError('OCR结果无可搜索文字，请人工核对')
            errors = [{'path': str(source), 'page': index + 1,
                       'reason': '该页无可搜索文字（可能空白、识别失败或超时），请人工核对ocr.log'}
                      for index, text in enumerate(page_texts) if not text]
            if digest(source) != checksum:
                raise ValueError('处理期间原件变化，请重试')
            with (work / 'searchable.pdf').open('rb') as read, (output / 'searchable.pdf').open('xb') as write:
                shutil.copyfileobj(read, write)
        save_json(output / 'provenance.json', {
            'source': str(source), 'source_sha256': checksum,
            'output_sha256': digest(output / 'searchable.pdf'),
            'note': 'OCR衍生副本，原件未修改；机器识别可能出错，需人工核对。',
        })
        save_json(output / 'errors.json', errors)
        return dict(output=str(output), failed=len(errors))
    except Exception as exc:
        save_json(output / 'errors.json', [{'path': str(source), 'reason': str(exc)}])
        raise
