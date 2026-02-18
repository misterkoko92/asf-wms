from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from .view_permissions import scan_staff_required

TEMPLATE_SCAN_FAQ = "scan/faq.html"
ACTIVE_FAQ = "faq"
SHELL_CLASS_WIDE = "scan-shell-wide"
SCAN_SW_ALLOWED_SCOPE = "/scan/"
CACHE_CONTROL_NO_CACHE = "no-cache"

SERVICE_WORKER_JS = """const CACHE_NAME = 'wms-scan-v37';
const ASSETS = [
  '/static/scan/scan.css',
  '/static/scan/scan.js',
  '/static/scan/zxing.min.js',
  '/static/scan/manifest.json',
  '/static/scan/icon.svg'
];

self.addEventListener('install', event => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(ASSETS))
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))
    )).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') {
    return;
  }
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request, { cache: 'no-store' })
        .catch(() => caches.match(event.request))
    );
    return;
  }
  event.respondWith(
    caches.match(event.request).then(response => response || fetch(event.request))
  );
});
"""


def _build_faq_context():
    return {
        "active": ACTIVE_FAQ,
        "shell_class": SHELL_CLASS_WIDE,
    }


def _build_service_worker_response():
    response = HttpResponse(SERVICE_WORKER_JS, content_type="application/javascript")
    response["Cache-Control"] = CACHE_CONTROL_NO_CACHE
    response["Service-Worker-Allowed"] = SCAN_SW_ALLOWED_SCOPE
    return response


@scan_staff_required
@require_http_methods(["GET"])
def scan_faq(request):
    return render(request, TEMPLATE_SCAN_FAQ, _build_faq_context())


def scan_service_worker(request):
    return _build_service_worker_response()
