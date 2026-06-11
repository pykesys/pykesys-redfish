from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import BMCHostViewSet

router = DefaultRouter()
router.register(r"hosts", BMCHostViewSet, basename="host")

urlpatterns = [
    path("", include(router.urls)),
]
