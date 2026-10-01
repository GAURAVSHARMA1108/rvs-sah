from django.urls import path
from .views import (
    AccountStatusAPIView,
    StartSessionAPIView,
    RefreshCaptchaAPIView,
    SubmitLoginAPIView,
    FetchStudentsAPIView,
    AutomatedFetchStudentsAPIView,
    CloseSessionAPIView,
)

app_name = 'scraper_api'

urlpatterns = [
    # Account status & quota inspection
    path('account/status', AccountStatusAPIView.as_view(), name='account_status'),

    # Interactive 2-Phase Session Workflow (Standard & Free Tier)
    path('session/start', StartSessionAPIView.as_view(), name='session_start'),
    path('session/refresh-captcha', RefreshCaptchaAPIView.as_view(), name='session_refresh_captcha'),
    path('session/login', SubmitLoginAPIView.as_view(), name='session_login'),
    path('session/fetch-students', FetchStudentsAPIView.as_view(), name='session_fetch_students'),
    path('session/close', CloseSessionAPIView.as_view(), name='session_close'),

    # Enterprise Automated Single-Call Sync (AI/OCR Auto-Captcha)
    path('automated/fetch-students', AutomatedFetchStudentsAPIView.as_view(), name='automated_fetch_students'),
]
