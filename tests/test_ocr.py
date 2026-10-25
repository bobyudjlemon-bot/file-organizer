import json
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader, PdfWriter

from file_organizer.core import digest, extract, preview, validate_rules
from file_organizer.ocr import extract_ocr, searchable_pdf


@pytest.fixture
def chinese_scan(tmp_path):
    font_path = Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
    assert font_path.is_file(), '测试需要fonts-noto-cjk字体'
    image = Image.new('RGB', (1600, 500), 'white')
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(font_path), 64)
    draw.text((80, 80), '采购合同 合同编号 2026001', fill='black', font=font)
    draw.text((80, 200), 'Invoice Total 12345', fill='black', font=font)
    png, pdf = tmp_path / 'scan.png', tmp_path / 'scan.pdf'
    image.save(png)
    image.save(pdf, resolution=200)
    image.close()
    return png, pdf


def test_real_chinese_image_and_pdf_ocr(chinese_scan):
    for path in chinese_scan:
        before = digest(path)
        text = extract(path, ocr=True)
        assert '合同' in text.replace(' ', '')
        assert '12345' in text
        assert digest(path) == before


def test_ocr_classification_is_preview_only(chinese_scan, tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    png, _ = chinese_scan
    (source / 'scan.png').write_bytes(png.read_bytes())
    plan = preview(source, tmp_path / 'preview', {
        'ocr': True, 'rules': [{'category': '合同', 'content_contains': ['合同']}]})
    assert plan['files'][0]['category'] == '合同'
    assert 'OCR' in plan['files'][0]['warning']
    assert not list((tmp_path / 'preview').rglob('*.png'))


def test_searchable_pdf_cli_and_original_preserved(chinese_scan, tmp_path):
    _, pdf = chinese_scan
    before = digest(pdf)
    output = tmp_path / 'result'
    result = subprocess.run([sys.executable, '-m', 'file_organizer', 'ocr-pdf', str(pdf), '--output', str(output), '--confirm'], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr + (output / 'ocr.log').read_text() if (output / 'ocr.log').exists() else result.stderr
    assert digest(pdf) == before
    assert '12345' in ''.join(p.extract_text() or '' for p in PdfReader(output / 'searchable.pdf').pages)
    assert json.loads((output / 'provenance.json').read_text())['source_sha256'] == before
    assert json.loads((output / 'errors.json').read_text()) == []
    with pytest.raises(FileExistsError):
        searchable_pdf(pdf, output, True)


def test_pdf_confirmation_required(chinese_scan, tmp_path):
    with pytest.raises(ValueError, match='确认'):
        searchable_pdf(chinese_scan[1], tmp_path / 'result')
    assert not (tmp_path / 'result').exists()


def test_encrypted_and_oversize_page_count(tmp_path):
    writer = PdfWriter()
    for _ in range(21):
        writer.add_blank_page(width=100, height=100)
    pdf = tmp_path / 'large.pdf'
    writer.write(pdf)
    with pytest.raises(ValueError, match='20页'):
        extract_ocr(pdf)
    writer.encrypt('password')
    writer.write(pdf)
    with pytest.raises(ValueError, match='加密'):
        searchable_pdf(pdf, tmp_path / 'output', True)


def test_timeout_is_recorded(chinese_scan, tmp_path, monkeypatch):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired('ocrmypdf', 300)
    monkeypatch.setattr('file_organizer.ocr.subprocess.run', timeout)
    with pytest.raises(subprocess.TimeoutExpired):
        searchable_pdf(chinese_scan[1], tmp_path / 'failed', True)
    assert '300' in (tmp_path / 'failed/errors.json').read_text()
    assert not (tmp_path / 'failed/searchable.pdf').exists()


def test_blank_image_fails_and_is_logged(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    Image.new('RGB', (100, 100), 'white').save(source / 'blank.png')
    plan = preview(source, tmp_path / 'preview', {'ocr': True, 'rules': [{'category': '合同', 'content_contains': ['合同']}]})
    assert plan['files'][0]['category'] == '图片'
    assert '未识别' in plan['files'][0]['warning']


def test_no_ocr_without_opt_in(chinese_scan):
    with pytest.raises(ValueError, match='不支持内容提取'):
        extract(chinese_scan[0])
    with pytest.raises(ValueError):
        validate_rules({'ocr': 'yes'})


def test_partial_pdf_records_unrecognized_page(chinese_scan, tmp_path):
    writer = PdfWriter()
    writer.append(chinese_scan[1])
    writer.add_blank_page(width=300, height=100)
    source = tmp_path / 'mixed.pdf'
    writer.write(source)
    result = searchable_pdf(source, tmp_path / 'partial', True)
    assert result['failed'] == 1
    errors = json.loads((tmp_path / 'partial/errors.json').read_text())
    assert errors[0]['page'] == 2
    assert (tmp_path / 'partial/searchable.pdf').is_file()


def test_traditional_chinese(tmp_path):
    image = Image.new('RGB', (1400, 300), 'white')
    font = ImageFont.truetype('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc', 72)
    ImageDraw.Draw(image).text((60, 80), '繁體中文 合約編號 2026002', fill='black', font=font)
    path = tmp_path / 'traditional.png'
    image.save(path)
    image.close()
    text = extract(path, ocr=True)
    assert '合約' in text.replace(' ', '')
    assert '2026002' in text
