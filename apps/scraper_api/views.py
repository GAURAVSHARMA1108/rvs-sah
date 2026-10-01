import time
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from apps.billing.permissions import HasActiveSubscriptionAndQuota, RequiresAutoCaptchaPlan
from apps.billing.models import UsageAuditLog
from .engine.browser_pool import browser_pool

class AccountStatusAPIView(APIView):
    """Returns current user account, subscription tier, and remaining monthly quota."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        sub = getattr(user, 'subscription', None)
        if not sub:
            return Response({
                "username": user.username,
                "plan": "No Plan Assigned",
                "tier": "NONE",
                "monthly_quota": 0,
                "used_this_month": 0,
                "quota_remaining": 0,
                "is_active": False
            })

        remaining = max(0, sub.plan.monthly_request_quota - sub.current_month_usage)
        return Response({
            "username": user.username,
            "plan": sub.plan.name,
            "tier": sub.plan.tier,
            "monthly_quota": sub.plan.monthly_request_quota,
            "used_this_month": sub.current_month_usage,
            "quota_remaining": remaining,
            "is_active": sub.is_active,
            "allows_auto_captcha": sub.plan.allows_auto_captcha,
            "allows_deep_scrape": sub.plan.allows_deep_scrape
        })


class StartSessionAPIView(APIView):
    """
    Initializes a new isolated browser session and captures the live CAPTCHA.
    Standard/Free tier entrypoint.
    """
    permission_classes = [HasActiveSubscriptionAndQuota]

    def post(self, request):
        res = browser_pool.create_session()
        if not res.get("success"):
            return Response(res, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(res, status=status.HTTP_201_CREATED)


class RefreshCaptchaAPIView(APIView):
    """Refreshes live portal CAPTCHA challenge for an active session."""
    permission_classes = [HasActiveSubscriptionAndQuota]

    def post(self, request):
        session_id = request.data.get("session_id", "").strip()
        if not session_id:
            return Response({"error": "Missing session_id in request body."}, status=status.HTTP_400_BAD_REQUEST)

        res = browser_pool.refresh_captcha(session_id)
        if not res.get("success"):
            return Response(res, status=status.HTTP_400_BAD_REQUEST)
        return Response(res, status=status.HTTP_200_OK)


class SubmitLoginAPIView(APIView):
    """Submits school credentials & CAPTCHA to authenticate session."""
    permission_classes = [HasActiveSubscriptionAndQuota]

    def post(self, request):
        data = request.data or {}
        session_id = data.get("session_id", "").strip()
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()
        captcha = data.get("captcha", "").strip()

        if not all([session_id, username, password, captcha]):
            return Response(
                {"error": "Missing required fields: session_id, username, password, and captcha are mandatory."},
                status=status.HTTP_400_BAD_REQUEST
            )

        res = browser_pool.submit_login(session_id, username, password, captcha)
        if not res.get("success"):
            return Response(res, status=status.HTTP_401_UNAUTHORIZED)
        return Response(res, status=status.HTTP_200_OK)


class FetchStudentsAPIView(APIView):
    """
    Extracts student records for selected Session and Class.
    Deducts 1 request credit from the monthly quota upon successful extraction.
    Zero sensitive student data is retained in the database.
    """
    permission_classes = [HasActiveSubscriptionAndQuota]

    def post(self, request):
        start_t = time.time()
        data = request.data or {}
        session_id = data.get("session_id", "").strip()
        session_val = data.get("session_val", "").strip()
        class_val = data.get("class_val", "").strip()
        deep_scrape = bool(data.get("deep_scrape", False))

        if not session_id or not session_val or not class_val:
            return Response(
                {"error": "session_id, session_val, and class_val are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        res = browser_pool.fetch_students(session_id, session_val, class_val, deep_scrape=deep_scrape)
        duration = round(time.time() - start_t, 2)

        user = request.user
        school_code = data.get("school_code", "")

        if res.get("success"):
            # Deduct quota credit
            if hasattr(user, 'subscription'):
                user.subscription.record_usage(1)

            # Record audit log (Strictly ZERO student personal data saved!)
            UsageAuditLog.objects.create(
                user=user,
                school_code=school_code,
                session_year=session_val,
                class_name=class_val,
                students_extracted=res.get("count", 0),
                execution_time_seconds=duration,
                status="SUCCESS"
            )

            # Append remaining quota in response
            remaining = getattr(user.subscription, 'plan', None)
            if remaining:
                res["quota_remaining"] = max(0, user.subscription.plan.monthly_request_quota - user.subscription.current_month_usage)

            return Response(res, status=status.HTTP_200_OK)
        else:
            UsageAuditLog.objects.create(
                user=user,
                school_code=school_code,
                session_year=session_val,
                class_name=class_val,
                students_extracted=0,
                execution_time_seconds=duration,
                status="FAILED",
                error_message=res.get("error", "Extraction error")
            )
            return Response(res, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AutomatedFetchStudentsAPIView(APIView):
    """
    Enterprise-Tier Single-Call Headless Sync:
    Uses local OCR to auto-solve CAPTCHA in background, logs in,
    and extracts student records with zero human interaction.
    """
    permission_classes = [HasActiveSubscriptionAndQuota, RequiresAutoCaptchaPlan]

    def post(self, request):
        start_t = time.time()
        data = request.data or {}
        school_code = data.get("school_code", "").strip()
        password = data.get("password", "").strip()
        session_val = data.get("session_val", "").strip()
        class_val = data.get("class_val", "").strip()

        if not all([school_code, password, session_val, class_val]):
            return Response(
                {"error": "school_code, password, session_val, and class_val are all required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        res = browser_pool.automated_fetch(school_code, password, session_val, class_val)
        duration = round(time.time() - start_t, 2)
        user = request.user

        if res.get("success"):
            if hasattr(user, 'subscription'):
                user.subscription.record_usage(1)

            UsageAuditLog.objects.create(
                user=user,
                school_code=school_code,
                session_year=session_val,
                class_name=class_val,
                students_extracted=res.get("count", 0),
                execution_time_seconds=duration,
                status="SUCCESS"
            )
            return Response(res, status=status.HTTP_200_OK)
        else:
            UsageAuditLog.objects.create(
                user=user,
                school_code=school_code,
                session_year=session_val,
                class_name=class_val,
                students_extracted=0,
                execution_time_seconds=duration,
                status="FAILED",
                error_message=res.get("error", "Automated sync failed")
            )
            return Response(res, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CloseSessionAPIView(APIView):
    """Releases active browser context immediately."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        session_id = request.data.get("session_id", "").strip()
        if session_id:
            browser_pool.close_session(session_id)
        return Response({"success": True, "message": "Session closed."})
