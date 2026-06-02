from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class UserLocation(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='bonnaroo_location')
    lat = models.FloatField()
    lng = models.FloatField()
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} @ ({self.lat}, {self.lng})"


class SharedLocation(models.Model):
    TAG_CHOICES = [
        ('', 'None'),
        ('food', 'Food'),
        ('water', 'Water'),
        ('stage', 'Stage'),
        ('bathroom', 'Bathroom'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='shared_locations')
    name = models.CharField(max_length=100)
    tag = models.CharField(max_length=20, blank=True, default='', choices=TAG_CHOICES)
    lat = models.FloatField()
    lng = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} by {self.user.get_full_name() or self.user.username}"
