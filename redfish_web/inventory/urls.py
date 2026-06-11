from django.urls import path
from .views import SnapshotViewSet, LogEntryViewSet, SensorViewSet, fleet_dashboard

urlpatterns = [
    path("fleet/", fleet_dashboard, name="fleet-dashboard"),
    path("hosts/<int:host_pk>/snapshots/", SnapshotViewSet.as_view({"get": "list"}), name="host-snapshots"),
    path("hosts/<int:host_pk>/snapshots/<int:pk>/", SnapshotViewSet.as_view({"get": "retrieve"}), name="host-snapshot-detail"),
    path("hosts/<int:host_pk>/logs/", LogEntryViewSet.as_view({"get": "list"}), name="host-logs"),
    path("hosts/<int:host_pk>/sensors/", SensorViewSet.as_view({"get": "list"}), name="host-sensors"),
]
