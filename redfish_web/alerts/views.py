from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone

from .models import AlertRule, AlertEvent
from .serializers import AlertRuleSerializer, AlertEventSerializer


class AlertRuleViewSet(viewsets.ModelViewSet):
    queryset = AlertRule.objects.all()
    serializer_class = AlertRuleSerializer


class AlertEventViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = AlertEventSerializer

    def get_queryset(self):
        qs = AlertEvent.objects.select_related("rule", "host").all()
        open_only = self.request.query_params.get("open")
        if open_only == "true":
            qs = qs.filter(resolved_at__isnull=True)
        host_id = self.request.query_params.get("host")
        if host_id:
            qs = qs.filter(host_id=host_id)
        return qs

    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None):
        event = self.get_object()
        if event.resolved_at:
            return Response({"error": "Already resolved"}, status=status.HTTP_400_BAD_REQUEST)
        event.resolved_at = timezone.now()
        event.save(update_fields=["resolved_at"])
        return Response(AlertEventSerializer(event).data)
