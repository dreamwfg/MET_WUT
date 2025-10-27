from rest_framework import generics, permissions

from .models import TestDate, Booking
from .serializers import TestDateSerializer, BookingSerializer, BookingListSerializer


class TestDateListAPIView(generics.ListAPIView):
    queryset = TestDate.objects.all().order_by('date')
    serializer_class = TestDateSerializer
    permission_classes = [permissions.AllowAny]


class BookingListCreateAPIView(generics.ListCreateAPIView):
    """List (only the booking dates for the requesting user) and create bookings.

    - GET: returns a list of objects shaped by `BookingListSerializer` (only `date`).
    - POST: accepts booking creation via `BookingSerializer`.
    """
    queryset = Booking.objects.none()
    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Return only bookings that belong to the requesting user
        user = self.request.user
        return Booking.objects.filter(user=user).select_related('test_date').order_by('-created_at')

    def get_serializer_class(self):
        # Use the lightweight serializer for listing (GET), full serializer for create (POST)
        if self.request.method == 'GET':
            return BookingListSerializer
        return BookingSerializer

    def perform_create(self, serializer):
        # Ensure the booking is created for the requesting user
        serializer.save(user=self.request.user)