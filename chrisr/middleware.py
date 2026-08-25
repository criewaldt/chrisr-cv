"""Response headers Django does not provide settings for.

Content-Security-Policy is the important one. It cannot forbid inline styles and
scripts here -- both pages are built with inline <style> and <script> blocks, and
retrofitting nonces across them is a larger change -- but it still blocks the thing
that actually matters: loading script from an origin we did not authorise. That is
the difference between a stored-XSS bug being an annoyance and being a breach.
"""
from django.conf import settings

# Only origins the site genuinely uses.
#   fonts.googleapis.com / fonts.gstatic.com -- webfonts on both public pages
#   img-src data: / blob:                    -- data-URI images in vendored CSS (admin, DRF)
CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline'",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com",
    "img-src 'self' data: blob:",
    "connect-src 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "object-src 'none'",
])

# Drop access to hardware and background APIs nothing here uses.
PERMISSIONS_POLICY = ", ".join([
    "accelerometer=()", "camera=()", "display-capture=()", "geolocation=()",
    "gyroscope=()", "magnetometer=()", "microphone=()", "payment=()", "usb=()",
    "interest-cohort=()",
])


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Content-Security-Policy", CSP)
        response.setdefault("Permissions-Policy", PERMISSIONS_POLICY)
        response.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        if not settings.DEBUG:
            # Belt and braces: Django emits this too when SECURE_HSTS_SECONDS is set,
            # but only on requests it considers secure.
            response.setdefault(
                "Strict-Transport-Security",
                f"max-age={getattr(settings, 'SECURE_HSTS_SECONDS', 3600)}")
        return response
