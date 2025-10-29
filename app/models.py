from django.db import models

from users.models import User


class TestDate(models.Model):
    date = models.DateField(unique=True)
    max_spots = models.PositiveIntegerField(default=40)
    time = models.TimeField(null=True, blank=True)

    def __str__(self):
        # include time for clarity
        if self.time:
            return f"{self.date} {self.time}"
        return f"{self.date}"

    @property
    def spots_left(self):
        booked = self.bookings.count()
        return max(self.max_spots - booked, 0)

    @property
    def is_full(self):
        return self.spots_left <= 0

class Booking(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    test_date = models.ForeignKey(TestDate, on_delete=models.CASCADE, related_name='bookings')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'test_date')

    # def __str__(self):
    #     return f"{self.user.username} → {self.test_date.date}"
