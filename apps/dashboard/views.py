import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from . import services
from security.access import clinical_access_required


@login_required
@clinical_access_required('read')
@ensure_csrf_cookie
@never_cache
def index_view(request):
    """
    Renders the clinical and epidemiological dashboard view.
    Supplies real aggregated patient evaluation records computed
    from the clinical PostgreSQL models across all 8 clinical blocks.
    """
    data = services.get_dashboard_evaluation_data()
    context = {
        'total_evaluated': data['total'],
        'summary_kpis': data['summary_kpis'],
        'module_kpis': data['module_kpis'],
        'available_years': data['years'],
        'available_categories': data['categories'],
        'available_institutions': data['institutions'],
        'available_fichas': data['fichas'],
        'records': data['records'],
        'boolean_fields': data['boolean_fields'],
        'unemi_only': getattr(settings, 'UNEMI', False),
    }
    return render(request, "dashboard/index.html", context)


@login_required
@clinical_access_required('read', api=True)
@never_cache
def api_dashboard_data(request):
    """
    JSON API endpoint returning the dynamic cohort records and slicer metadata
    computed from real database records.
    """
    data = services.get_dashboard_evaluation_data()
    return JsonResponse({
        'status': 'success',
        'total': data['total'],
        'summary_kpis': data['summary_kpis'],
        'module_kpis': data['module_kpis'],
        'years': data['years'],
        'categories': data['categories'],
        'institutions': data['institutions'],
        'fichas': data['fichas'],
        'records': data['records'],
        'boolean_fields': data['boolean_fields'],
        'unemi_only': getattr(settings, 'UNEMI', False),
    })


def _dashboard_chrome_binary():
    """Return a locally installed Chromium binary used for real HTML-to-PDF conversion."""
    configured = os.environ.get('DASHBOARD_CHROME_BINARY', '').strip()
    candidates = [configured] if configured else []
    candidates.extend([
        shutil.which('chrome'),
        shutil.which('google-chrome'),
        shutil.which('chromium'),
        shutil.which('chromium-browser'),
        r'C:\Program Files\Google\Chrome\Application\chrome.exe',
        r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
        r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
        r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    ])
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    return None


@login_required
@clinical_access_required('read')
@require_POST
@never_cache
def export_dashboard_html_pdf(request):
    """Convert the dashboard's self-contained HTML report into a vector PDF.

    The browser builds the report HTML from the same dashboard sections. This
    endpoint only invokes a fixed local Chromium executable; it never accepts a
    command or URL from the client and rejects scripts in the submitted report.
    """
    max_payload = 48 * 1024 * 1024
    content_length = request.META.get('CONTENT_LENGTH', '').strip()
    if content_length:
        try:
            declared_length = int(content_length)
        except ValueError:
            return JsonResponse({'error': 'El tamaño del reporte HTML no es válido.'}, status=400)
        if declared_length < 0:
            return JsonResponse({'error': 'El tamaño del reporte HTML no es válido.'}, status=400)
        if declared_length > max_payload:
            return JsonResponse({'error': 'El reporte HTML supera el tamaño permitido.'}, status=413)

    # Leer con un límite propio para no activar DATA_UPLOAD_MAX_MEMORY_SIZE global.
    raw_body = request.read(max_payload + 1)
    if len(raw_body) > max_payload:
        return JsonResponse({'error': 'El reporte HTML supera el tamaño permitido.'}, status=413)

    try:
        payload = json.loads(raw_body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({'error': 'El reporte HTML no es válido.'}, status=400)

    report_html = payload.get('html') if isinstance(payload, dict) else None
    if not isinstance(report_html, str) or not report_html.strip():
        return JsonResponse({'error': 'No se recibió el reporte HTML.'}, status=400)
    if '<script' in report_html.lower() or '<iframe' in report_html.lower():
        return JsonResponse({'error': 'El reporte contiene contenido no permitido.'}, status=400)

    chrome = _dashboard_chrome_binary()
    if not chrome:
        return JsonResponse({
            'error': 'No hay un navegador Chromium disponible para convertir el HTML a PDF.'
        }, status=503)

    try:
        with tempfile.TemporaryDirectory(prefix='cardiounemi-dashboard-export-') as workdir:
            work_path = Path(workdir)
            html_path = work_path / 'report.html'
            pdf_path = work_path / 'report.pdf'
            profile_path = work_path / 'profile'
            html_path.write_text(report_html, encoding='utf-8')

            command = [
                chrome,
                '--headless=new',
                '--disable-gpu',
                '--disable-extensions',
                '--no-first-run',
                '--disable-background-networking',
                '--disable-sync',
                '--allow-file-access-from-files',
                '--force-device-scale-factor=2',
                '--no-pdf-header-footer',
                '--run-all-compositor-stages-before-draw',
                '--virtual-time-budget=2000',
                f'--user-data-dir={profile_path}',
                f'--print-to-pdf={pdf_path}',
                html_path.as_uri(),
            ]
            if hasattr(os, 'geteuid') and os.geteuid() == 0:
                command.insert(2, '--no-sandbox')

            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=90,
                check=False,
            )
            if completed.returncode != 0 or not pdf_path.is_file():
                return JsonResponse({'error': 'Chromium no pudo convertir el reporte HTML a PDF.'}, status=503)
            pdf_bytes = pdf_path.read_bytes()
    except subprocess.TimeoutExpired:
        return JsonResponse({'error': 'La conversión HTML a PDF excedió el tiempo permitido.'}, status=504)
    except OSError:
        return JsonResponse({'error': 'No se pudo ejecutar el conversor HTML a PDF.'}, status=503)

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="CardioUNEMI_Dashboard.pdf"'
    response['Content-Length'] = str(len(pdf_bytes))
    return response
