from django.urls import path

from .views import *

urlpatterns = [
    path('dates/', TestDateListAPIView.as_view(), name='test-dates'),
    path('bookings/', BookingListCreateAPIView.as_view(), name='bookings'),
]
