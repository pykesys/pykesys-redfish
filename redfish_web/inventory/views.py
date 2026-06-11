from rest_framework import viewsets, mixins
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from hosts.models import BMCHost
from hosts.serializers import BMCHostListSerializer
from .models import InventorySnapshot, SensorReading, LogEntry
from .serializers import (
    InventorySnapshotSerializer,
    InventorySnapshotSummarySerializer,
    SensorReadingSerializer,
    LogEntrySerializer,
)


class SnapshotViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = InventorySnapshotSummarySerializer

    def get_queryset(self):
        host_id = self.kwargs.get("host_pk")
        qs = InventorySnapshot.objects.select_related("host")
        if host_id:
            qs = qs.filter(host_id=host_id)
        return qs

    def get_serializer_class(self):
        if self.action == "retrieve":
            return InventorySnapshotSerializer
        return InventorySnapshotSummarySerializer


class LogEntryViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = LogEntrySerializer

    def get_queryset(self):
        host_id = self.kwargs.get("host_pk")
        qs = LogEntry.objects.select_related("host")
        if host_id:
            qs = qs.filter(host_id=host_id)
        return qs


class SensorViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = SensorReadingSerializer

    def get_queryset(self):
        host_id = self.kwargs.get("host_pk")
        if host_id:
            latest = (
                InventorySnapshot.objects.filter(host_id=host_id).order_by("-polled_at").first()
            )
            if latest:
                return SensorReading.objects.filter(snapshot=latest)
        return SensorReading.objects.none()


@api_view(["GET"])
def fleet_dashboard(request):
    """Return all hosts with their latest snapshot embedded."""
    hosts = BMCHost.objects.all()
    result = []
    for host in hosts:
        latest = host.snapshots.first()
        host_data = BMCHostListSerializer(host).data
        host_data["latest_snapshot"] = (
            InventorySnapshotSummarySerializer(latest).data if latest else None
        )
        result.append(host_data)
    return Response(result)
