from rest_framework import serializers
from .models import BMCHost


class BMCHostSerializer(serializers.ModelSerializer):
    class Meta:
        model = BMCHost
        fields = [
            "id", "host", "display_name", "username", "password",
            "verify_ssl", "enabled", "poll_interval", "tags",
            "last_seen", "last_error", "created_at", "updated_at",
        ]
        extra_kwargs = {"password": {"write_only": True}}


class BMCHostListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views — omits password."""
    class Meta:
        model = BMCHost
        fields = [
            "id", "host", "display_name", "username",
            "verify_ssl", "enabled", "poll_interval", "tags",
            "last_seen", "last_error",
        ]
