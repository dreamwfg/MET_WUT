from django.contrib import admin
from django.db.models import Count, F, IntegerField, ExpressionWrapper

from .models import TestDate, Booking


@admin.register(TestDate)
class TestDateAdmin(admin.ModelAdmin):
    list_display = ("date", "time", "max_spots", "spots_left_display")
    list_editable = ("max_spots", "time")
    readonly_fields = ("spots_left_display",)
    list_filter = ("date",)
    ordering = ("date", "time")
    search_fields = ("date", "time")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(booked=Count('bookings'))
        qs = qs.annotate(spots_left_ann=ExpressionWrapper(F('max_spots') - F('booked'), output_field=IntegerField()))
        return qs

    @admin.display(ordering='spots_left_ann', description="spots left")
    def spots_left_display(self, obj):
        val = getattr(obj, 'spots_left_ann', None)
        if val is None:
            return obj.spots_left
        return max(int(val), 0)


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("user", "test_date", "created_at")
    search_fields = ("user__username",)
    list_filter = ("test_date",)


