# decoder/models.py
from django.db import models
from django.utils import timezone


class PocsagMessage(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    address = models.CharField(max_length=50)
    function = models.CharField(max_length=10)
    message = models.TextField()
    raw_data = models.TextField(blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.timestamp} - {self.address}: {self.message[:50]}"


class ListenerStatus(models.Model):
    is_running = models.BooleanField(default=False)
    last_heartbeat = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "Listener Status"

    @classmethod
    def get_status(cls):
        status, created = cls.objects.get_or_create(id=1)
        if status.last_heartbeat:
            offline_threshold = timezone.now() - timezone.timedelta(seconds=10)
            if status.last_heartbeat < offline_threshold:
                status.is_running = False
                status.save()
        return status

    @classmethod
    def set_running(cls, running=True):
        status = cls.get_status()
        status.is_running = running
        if running:
            status.started_at = timezone.now()
        else:
            status.started_at = None
        status.save()
        return status

    @classmethod
    def heartbeat(cls):
        status = cls.get_status()
        status.is_running = True
        status.save()
