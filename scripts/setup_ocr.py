"""Install pinned upstream Tesseract models with SHA-256 verification."""
import hashlib
import os
from pathlib import Path
import shutil
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
REVISION = '87416418657359cb625c412a48b6e1d6d41c29bd'
MODELS = {
    'chi_sim': 'a5fcb6f0db1e1d6d8522f39db4e848f05984669172e584e8d76b6b3141e1f730',
    'chi_tra': '529c5b5797d64b126065cd55f2bb4c7fd7b15790798091b1ff259941a829330b',
    'eng': '7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2',
}


def main():
    if not shutil.which('tesseract'):
        raise SystemExit('缺少系统依赖。Ubuntu: sudo apt-get install tesseract-ocr fonts-noto-cjk')
    target = ROOT / '.ocr' / 'tessdata'
    target.mkdir(parents=True, exist_ok=True)
    configs = next((p for p in [Path('/usr/share/tesseract-ocr/5/tessdata/configs'),
                               Path('/usr/share/tesseract-ocr/4.00/tessdata/configs'),
                               Path('/usr/share/tessdata/configs'),
                               Path('/usr/local/share/tessdata/configs')]
                    if (p / 'hocr').is_file()), None)
    if configs is None:
        raise SystemExit('缺少Tesseract标准configs/hocr，请安装完整tesseract-ocr系统包')
    shutil.copytree(configs, target / 'configs', dirs_exist_ok=True)
    for lang, expected in MODELS.items():
        path = target / f'{lang}.traineddata'
        if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == expected:
            print(f'{lang}: 校验通过')
            continue
        url = f'https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/{REVISION}/{lang}.traineddata'
        with urllib.request.urlopen(url, timeout=60) as response:
            data = response.read(20 * 1024 * 1024)
        if hashlib.sha256(data).hexdigest() != expected:
            raise SystemExit(f'{lang}: 校验失败，停止安装')
        fd, temporary = tempfile.mkstemp(dir=target)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(data)
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)
        print(f'{lang}: 安装且校验通过')


if __name__ == '__main__':
    main()
