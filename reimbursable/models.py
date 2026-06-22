import secrets
import string

from django.db import models


class Session(models.Model):
    code = models.CharField(max_length=8, unique=True, db_index=True)
    name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.code})"

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self._generate_code()
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_code():
        alphabet = string.ascii_lowercase + string.digits
        for _ in range(10):
            code = ''.join(secrets.choice(alphabet) for _ in range(8))
            if not Session.objects.filter(code=code).exists():
                return code
        raise RuntimeError("Failed to generate unique session code")


class Participant(models.Model):
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='participants')
    name = models.CharField(max_length=100)

    class Meta:
        unique_together = ('session', 'name')

    def __str__(self):
        return self.name


class Payment(models.Model):
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='payments')
    paid_by = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name='payments_made')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    to_entity = models.CharField(max_length=200, blank=True, default='')
    to_participant = models.ForeignKey(
        Participant, on_delete=models.CASCADE,
        related_name='payments_received', null=True, blank=True,
    )
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        target = self.to_participant.name if self.to_participant else self.to_entity
        return f"{self.paid_by.name} paid ${self.amount} → {target}"

    @property
    def is_direct(self):
        return self.to_participant is not None
