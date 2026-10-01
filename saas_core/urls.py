from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

admin.site.site_header = "RVS SAH Administration"
admin.site.site_title = "RVS SAH Admin"
admin.site.index_title = "Welcome to RVS SAH Management Portal"

from apps.widget.views import LLMsTxtView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('apps.scraper_api.urls')),
    path('widget/', include('apps.widget.urls')),
    path('llms.txt', LLMsTxtView.as_view(), name='llms_txt'),
    path('llms-full.txt', LLMsTxtView.as_view(), name='llms_full_txt'),
    path('', RedirectView.as_view(url='/widget/demo/', permanent=False)),
]
