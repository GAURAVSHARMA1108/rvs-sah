from django.urls import path
from .views import WidgetDemoView, DeveloperDocsView

app_name = 'widget'

urlpatterns = [
    path('demo/', WidgetDemoView.as_view(), name='demo'),
    path('docs/', DeveloperDocsView.as_view(), name='docs'),
]
