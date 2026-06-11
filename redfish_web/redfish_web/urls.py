from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic import TemplateView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("hosts.urls")),
    path("api/", include("inventory.urls")),
    path("api/", include("alerts.urls")),
    # SPA catch-all — must be last
    re_path(r"^(?!api/|admin/|static/).*$", TemplateView.as_view(template_name="index.html")),
]
