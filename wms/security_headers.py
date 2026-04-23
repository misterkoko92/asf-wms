from django.conf import settings

CSP_REPORT_ONLY_HEADER = "Content-Security-Policy-Report-Only"


class ContentSecurityPolicyReportOnlyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not getattr(settings, "CSP_REPORT_ONLY_ENABLED", True):
            return response

        policy = str(getattr(settings, "CONTENT_SECURITY_POLICY_REPORT_ONLY", "") or "").strip()
        if policy and not response.has_header(CSP_REPORT_ONLY_HEADER):
            response[CSP_REPORT_ONLY_HEADER] = policy
        return response
