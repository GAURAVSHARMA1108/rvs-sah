from django.db import models
from django.conf import settings
from django.utils import timezone

class PlanTier(models.TextChoices):
    FREE = 'FREE', 'Free Trial'
    STANDARD = 'STANDARD', 'Standard (Interactive Captcha)'
    ENTERPRISE = 'ENTERPRISE', 'Enterprise (Auto-Captcha & High Quota)'


class Plan(models.Model):
    name = models.CharField(max_length=60, unique=True)
    tier = models.CharField(max_length=20, choices=PlanTier.choices, default=PlanTier.STANDARD)
    monthly_request_quota = models.PositiveIntegerField(
        default=100,
        help_text="Maximum student extraction requests permitted per calendar month."
    )
    allows_auto_captcha = models.BooleanField(
        default=False,
        help_text="If enabled, allows Enterprise AI/OCR auto-captcha single-step sync."
    )
    allows_deep_scrape = models.BooleanField(
        default=True,
        help_text="Allows extracting detailed sub-profile forms (Aadhaar, Jan Aadhaar, Bank Details)."
    )
    max_concurrent_sessions = models.PositiveIntegerField(
        default=2,
        help_text="Maximum simultaneous active browser sessions."
    )
    price_inr = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Monthly price in INR")

    def __str__(self):
        return f"{self.name} ({self.tier}) - {self.monthly_request_quota} req/mo"


class Subscription(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name='subscriptions')
    is_active = models.BooleanField(default=True)
    current_month_usage = models.PositiveIntegerField(default=0)
    billing_cycle_anchor = models.DateField(default=timezone.now)
    notes = models.TextField(blank=True, help_text="Offline payment reference, UPI txn ID, or invoice number.")

    def __str__(self):
        return f"{self.user.username} - {self.plan.name} ({self.current_month_usage}/{self.plan.monthly_request_quota})"

    def has_quota(self) -> bool:
        """Checks if subscription is active and within monthly request limits."""
        if not self.is_active:
            return False
        return self.current_month_usage < self.plan.monthly_request_quota

    def record_usage(self, count: int = 1):
        """Atomically increments monthly usage count."""
        self.current_month_usage += count
        self.save(update_fields=['current_month_usage'])

    def reset_usage(self):
        """Resets the usage counter for a new billing cycle."""
        self.current_month_usage = 0
        self.billing_cycle_anchor = timezone.now().date()
        self.save(update_fields=['current_month_usage', 'billing_cycle_anchor'])


class UsageAuditLog(models.Model):
    """
    Zero-Data-Retention Audit Log.
    Logs ONLY operational metadata for billing verification and debugging.
    Strictly ZERO sensitive student personal details (Aadhaar, names, phone) stored!
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='usage_logs')
    timestamp = models.DateTimeField(auto_now_add=True)
    school_code = models.CharField(max_length=30)
    session_year = models.CharField(max_length=30, blank=True)
    class_name = models.CharField(max_length=30, blank=True)
    students_extracted = models.PositiveIntegerField(default=0)
    execution_time_seconds = models.FloatField(default=0.0)
    status = models.CharField(max_length=20, default='SUCCESS', choices=[
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
        ('ABORTED', 'Aborted')
    ])
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Usage Audit Log"
        verbose_name_plural = "Usage Audit Logs"

    def __str__(self):
        return f"[{self.timestamp.strftime('%Y-%m-%d %H:%M')}] {self.user.username} - {self.school_code} ({self.students_extracted} students)"
