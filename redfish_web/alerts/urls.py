from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AlertRuleViewSet, AlertEventViewSet

router = DefaultRouter()
router.register(r"alerts/rules", AlertRuleViewSet, basename="alert-rule")
router.register(r"alerts/events", AlertEventViewSet, basename="alert-event")

urlpatterns = [path("", include(router.urls))]
