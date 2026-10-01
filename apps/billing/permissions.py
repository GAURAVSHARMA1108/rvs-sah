from rest_framework import permissions, exceptions

class HasActiveSubscriptionAndQuota(permissions.BasePermission):
    """
    Permission check verifying that the authenticated user has an active subscription
    and has not exceeded their monthly request quota.
    """
    message = "You have reached your monthly request quota. Please upgrade or renew your plan."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        # Superusers bypass quota checks for administration/testing
        if user.is_superuser:
            return True

        subscription = getattr(user, 'subscription', None)
        if not subscription:
            from .models import Plan, PlanTier, Subscription
            free_plan = Plan.objects.filter(tier=PlanTier.FREE).first() or Plan.objects.first()
            if free_plan:
                subscription, _ = Subscription.objects.get_or_create(user=user, defaults={'plan': free_plan, 'is_active': True})
                user.subscription = subscription

        if not subscription or not subscription.is_active:
            raise exceptions.PermissionDenied(
                detail="No active subscription plan found. Contact administrator to assign a plan."
            )

        if not subscription.has_quota():
            raise exceptions.Throttled(
                detail=f"Monthly quota limit ({subscription.plan.monthly_request_quota} requests) reached for plan '{subscription.plan.name}'. Please contact support to upgrade."
            )

        return True


class RequiresAutoCaptchaPlan(permissions.BasePermission):
    """Permission check ensuring the user's plan supports automated AI/OCR CAPTCHA solving."""
    message = "Automated AI/OCR Captcha solving requires an Enterprise subscription plan."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True

        subscription = getattr(user, 'subscription', None)
        if not subscription or not subscription.plan.allows_auto_captcha:
            raise exceptions.PermissionDenied(detail=self.message)

        return True
