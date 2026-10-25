"""Office document to PDF conversion for inline browser preview.

LibreOffice is a system binary, not a Python package, so it is installed at
build time (see ``Dockerfile`` and ``nixpacks.toml``). When it is missing the
conversion quietly returns ``None`` and the upload still succeeds with the
original file; the viewer then falls back to whatever the browser can render.

The converter reads from Django's storage abstraction, so it works both with a
local ``MEDIA_ROOT`` and with S3/object storage where ``FieldFile.path`` does
not exist.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

CONVERTIBLE_EXTENSIONS = {'ppt', 'pptx', 'doc', 'docx', 'xls', 'xlsx'}

_TIMEOUT_SECONDS = 180


def find_libreoffice():
    """Return the path to a LibreOffice/soffice binary, or ``None``."""
    candidates = []
    for base in [
        os.environ.get('LIBREOFFICE_PATH'),
        os.environ.get('SOFFICE_PATH'),
        r'C:\Program Files\LibreOffice\program\soffice.exe',
        r'C:\Program Files (x86)\LibreOffice\program\soffice.exe',
        '/usr/bin/soffice',
        '/usr/bin/libreoffice',
        '/usr/local/bin/soffice',
        '/snap/bin/libreoffice',
        '/opt/libreoffice/program/soffice',
    ]:
        if base and os.path.exists(base):
            candidates.append(base)
    for name in ('soffice', 'libreoffice'):
        found = shutil.which(name)
        if found:
            candidates.append(found)
    return candidates[0] if candidates else None


def is_convertible_filename(filename):
    name = (filename or '').lower()
    return '.' in name and name.rsplit('.', 1)[-1] in CONVERTIBLE_EXTENSIONS


def _read_field_file_to_temp(field_file, work_dir):
    """Copy ``field_file`` into ``work_dir`` and return the local path."""
    suffix = Path(field_file.name or 'upload').suffix
    local_path = os.path.join(work_dir, f'source{suffix}')
    try:
        with field_file.open('rb') as source, open(local_path, 'wb') as target:
            shutil.copyfileobj(source, target, length=1024 * 1024)
    except (OSError, ValueError):
        return None
    return local_path if os.path.exists(local_path) else None


def convert_field_file_to_pdf_bytes(field_file):
    """Convert a stored ``FieldFile`` to PDF bytes, or return ``None``.

    Returns ``None`` when the file is not convertible, LibreOffice is not
    available, or the conversion fails for any reason.
    """
    if not field_file or not field_file.name:
        return None
    if not is_convertible_filename(field_file.name):
        return None
    soffice = find_libreoffice()
    if not soffice:
        return None

    work_dir = tempfile.mkdtemp(prefix='adom-convert-')
    try:
        input_path = _read_field_file_to_temp(field_file, work_dir)
        if not input_path:
            return None
        output_dir = os.path.join(work_dir, 'out')
        os.makedirs(output_dir, exist_ok=True)
        profile_dir = Path(work_dir, 'profile').as_uri()
        cmd = [
            soffice,
            '--headless',
            '--invisible',
            '--nofirststartwizard',
            '--nologo',
            '--nodefault',
            '--nolockcheck',
            f'-env:UserInstallation={profile_dir}',
            '--convert-to', 'pdf:writer_pdf_Export',
            '--outdir', output_dir,
            input_path,
        ]
        try:
            subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=_TIMEOUT_SECONDS,
                env={**os.environ, 'HOME': work_dir},
            )
        except (OSError, subprocess.SubprocessError):
            return None
        base = os.path.splitext(os.path.basename(input_path))[0]
        pdf_path = os.path.join(output_dir, base + '.pdf')
        if not os.path.exists(pdf_path):
            return None
        with open(pdf_path, 'rb') as pdf_file:
            data = pdf_file.read()
        return data or None
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def convert_to_pdf(input_path, output_dir=None):
    """Convert a local path to a PDF path (kept for management scripts/tests)."""
    soffice = find_libreoffice()
    if not soffice or not os.path.exists(input_path):
        return None
    if output_dir is None:
        output_dir = os.path.dirname(input_path)
    profile_dir = Path(tempfile.mkdtemp(prefix='adom-lo-profile-')).as_uri()
    cmd = [
        soffice,
        '--headless',
        '--invisible',
        '--nofirststartwizard',
        '--nologo',
        '--nodefault',
        '--nolockcheck',
        f'-env:UserInstallation={profile_dir}',
        '--convert-to', 'pdf:writer_pdf_Export',
        '--outdir', output_dir,
        input_path,
    ]
    try:
        subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    base = os.path.splitext(os.path.basename(input_path))[0]
    pdf_path = os.path.join(output_dir, base + '.pdf')
    return pdf_path if os.path.exists(pdf_path) else None
