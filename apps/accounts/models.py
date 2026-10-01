import secrets
import hashlib
from django.db import models
from django.conf import settings

class Organization(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='organization')
    company_name = models.CharField(max_length=150, help_text="School Name, ERP Provider, or Developer Name")
    contact_phone = models.CharField(max_length=20, blank=True)
    allowed_domains = models.TextField(
        default="*",
        help_text="Comma-separated domains allowed to embed the widget (e.g. myschool.com, *.erp.in) or * for all."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.company_name} ({self.user.username})"


class APIKey(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='api_keys')
    name = models.CharField(max_length=100, default="Production API Key")
    key_prefix = models.CharField(max_length=24, db_index=True)
    key_hash = models.CharField(max_length=128, db_index=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "API Key"
        verbose_name_plural = "API Keys"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} [{self.key_prefix}...]"

    @classmethod
    def generate(cls, user, name="Production API Key"):
        """Generates a secure random API key token, hashes it, and stores the hash."""
        raw_token = f"sk_live_{secrets.token_urlsafe(32)}"
        prefix = raw_token[:16]
        hashed = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
        key_obj = cls.objects.create(
            user=user,
            name=name,
            key_prefix=prefix,
            key_hash=hashed
        )
        return key_obj, raw_token

    def verify_token(self, raw_token: str) -> bool:
        """Verifies if the provided token matches this key's hash."""
        target_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
        return secrets.compare_digest(self.key_hash, target_hash)
