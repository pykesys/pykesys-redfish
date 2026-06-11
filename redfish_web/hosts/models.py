from django.db import models


class BMCHost(models.Model):
    host = models.CharField(max_length=255, unique=True, help_text="https://bmc-host or bare hostname")
    display_name = models.CharField(max_length=255, blank=True)
    username = models.CharField(max_length=100)
    password = models.CharField(max_length=255)
    verify_ssl = models.BooleanField(default=True)
    enabled = models.BooleanField(default=True)
    poll_interval = models.IntegerField(default=300, help_text="Seconds between polls")
    tags = models.JSONField(default=list, blank=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["host"]

    def __str__(self):
        return self.display_name or self.host

    @property
    def base_url(self) -> str:
        if self.host.startswith("http"):
            return self.host
        return f"https://{self.host}"
