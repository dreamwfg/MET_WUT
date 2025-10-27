from rest_framework import serializers
from .models import TestDate, Booking
from zoneinfo import ZoneInfo

class TestDateSerializer(serializers.ModelSerializer):
    spots_left = serializers.IntegerField(read_only=True)
    is_full = serializers.BooleanField(read_only=True)
    date = serializers.DateField(format="%Y-%m-%d")
    time = serializers.TimeField(format="%H:%M", allow_null=True)

    class Meta:
        model = TestDate
        fields = ['id', 'date', 'time', 'max_spots', 'spots_left', 'is_full']



class BookingListSerializer(serializers.Serializer):
    date = serializers.DateField(source='test_date.date', read_only=True, format="%Y-%m-%d")
    time = serializers.TimeField(source='test_date.time', read_only=True, format="%H:%M", allow_null=True)


class BookingSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    test_date = serializers.PrimaryKeyRelatedField(
        queryset=TestDate.objects.all(),
        write_only=True
    )
    test_date_info = TestDateSerializer(source='test_date', read_only=True)

    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M", read_only=True)

    class Meta:
        model = Booking
        fields = ['id', 'user', 'test_date', 'test_date_info', 'created_at']
        read_only_fields = ['id', 'created_at', 'test_date_info']

    def validate(self, data):
        test_date = data['test_date']
        user = self.context['request'].user

        if test_date.is_full:
            raise serializers.ValidationError({"test_date": "No spots left for this date."})

        if Booking.objects.filter(user=user, test_date=test_date).exists():
            raise serializers.ValidationError("You have already booked this test date.")

        return data

    def create(self, validated_data):
        return Booking.objects.create(**validated_data)
