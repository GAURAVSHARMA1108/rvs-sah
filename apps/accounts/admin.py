from django.contrib import admin, messages
from django.utils.html import format_html
from .models import APIKey, Organization

class OrganizationInline(admin.StackedInline):
    model = Organization
    can_delete = False
    verbose_name_plural = 'Organization Profile'


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'key_prefix_display', 'is_active', 'created_at', 'last_used_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'user__username', 'key_prefix')
    readonly_fields = ('key_prefix', 'key_hash', 'created_at', 'last_used_at')
    actions = ['regenerate_key_action']

    def key_prefix_display(self, obj):
        return format_html("<code>{}...</code>", obj.key_prefix)
    key_prefix_display.short_description = "Key Prefix"

    def save_model(self, request, obj, form, change):
        if not change:
            import secrets, hashlib
            raw_token = f"sk_live_{secrets.token_urlsafe(32)}"
            obj.key_prefix = raw_token[:16]
            obj.key_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
            super().save_model(request, obj, form, change)
            messages.success(
                request,
                format_html(
                    "<strong>API Key Generated Successfully!</strong><br>"
                    "Copy this secret token now. It will NEVER be shown again:<br>"
                    "<div style='margin-top:8px; padding:10px; background:#0057FF; color:#fff; font-family:monospace; font-size:14px; border-radius:4px; user-select:all;'>{}</div>",
                    raw_token
                )
            )
        else:
            super().save_model(request, obj, form, change)

    @admin.action(description="Regenerate secret token for selected API key")
    def regenerate_key_action(self, request, queryset):
        import secrets, hashlib
        for key_obj in queryset:
            raw_token = f"sk_live_{secrets.token_urlsafe(32)}"
            key_obj.key_prefix = raw_token[:16]
            key_obj.key_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
            key_obj.is_active = True
            key_obj.save()
            messages.success(
                request,
                format_html(
                    "<strong>New API Key Generated for {}:</strong><br>"
                    "<div style='margin-top:8px; padding:10px; background:#0057FF; color:#fff; font-family:monospace; font-size:14px; border-radius:4px; user-select:all;'>{}</div>",
                    key_obj.user.username,
                    raw_token
                )
            )


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'user', 'contact_phone', 'created_at')
    search_fields = ('company_name', 'user__username', 'contact_phone')
