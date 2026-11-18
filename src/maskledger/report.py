"""Offline report writer. Metrics come only from the audit result."""
import json
from importlib.resources import files
from pathlib import Path
from .errors import InputError
from .output import output_transaction


def _web_numbers(value):
    # JSON files retain integer IDs; JS Number cannot exactly represent every ID.
    if type(value) is int and abs(value) > 2**53-1:
        return str(value)
    if isinstance(value, list):
        return [_web_numbers(v) for v in value]
    if isinstance(value, dict):
        return {k:_web_numbers(v) for k,v in value.items()}
    return value


def write_report(report, output_dir):
    with output_transaction(output_dir) as staging:
        _write_into(report, staging)


def _write_into(report, output_dir):
    output_dir = Path(output_dir)
    try:
        archive = json.dumps(report, ensure_ascii=True, allow_nan=False, indent=2)
        encoded = json.dumps(_web_numbers(report), ensure_ascii=True, allow_nan=False, separators=(',', ':'))
    except (ValueError, TypeError, UnicodeError) as exc:
        raise InputError('report cannot be safely serialized') from exc
    page = files('maskledger').joinpath('templates/report.html').read_text(encoding='utf-8')
    page = page.replace('__REPORT_DATA__', encoded.replace('<', '\\u003c'))
    (output_dir/'report.json').write_text(archive, encoding='utf-8')
    (output_dir/'index.html').write_text(page, encoding='utf-8')
