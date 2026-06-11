from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone

from .models import BMCHost
from .serializers import BMCHostSerializer, BMCHostListSerializer


class BMCHostViewSet(viewsets.ModelViewSet):
    queryset = BMCHost.objects.all()

    def get_serializer_class(self):
        if self.action == "list":
            return BMCHostListSerializer
        return BMCHostSerializer

    @action(detail=True, methods=["post"])
    def poll(self, request, pk=None):
        """Trigger an immediate out-of-cycle poll for this host."""
        host = self.get_object()
        from inventory.tasks import poll_host
        result = poll_host(host)
        if result.get("error"):
            return Response({"error": result["error"]}, status=status.HTTP_502_BAD_GATEWAY)
        return Response({"status": "polled", "snapshot_id": result.get("snapshot_id")})

    @action(detail=True, methods=["post"])
    def power(self, request, pk=None):
        """Send a power action: { reset_type: "GracefulRestart" }"""
        host = self.get_object()
        reset_type = request.data.get("reset_type")
        if not reset_type:
            return Response({"error": "reset_type required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            from pykesys_redfish import RedfishClient
            with RedfishClient(host.base_url, host.username, host.password, verify_ssl=host.verify_ssl) as rf:
                rf.system().reset(reset_type)
            return Response({"status": "sent", "reset_type": reset_type})
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

    @action(detail=True, methods=["post"])
    def boot(self, request, pk=None):
        """Set boot override: { target: "Pxe", enabled: "Once" }"""
        host = self.get_object()
        target = request.data.get("target")
        enabled = request.data.get("enabled", "Once")
        if not target:
            return Response({"error": "target required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            from pykesys_redfish import RedfishClient
            with RedfishClient(host.base_url, host.username, host.password, verify_ssl=host.verify_ssl) as rf:
                if enabled == "Disabled" or target == "None":
                    rf.system().clear_boot_override()
                else:
                    rf.system().set_boot_once(target)
            return Response({"status": "sent", "target": target, "enabled": enabled})
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
