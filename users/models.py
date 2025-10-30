from django.contrib.auth.base_user import BaseUserManager, AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin
from django.core.cache import cache
from django.db import models
import threading
import logging

logger = logging.getLogger(__name__)


# python
from django.contrib.auth.base_user import BaseUserManager

class CustomUserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, first_name, last_name, password=None, **extra_fields):
        if not email:
            raise ValueError('Users must have an email address')
        email = self.normalize_email(email)
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        extra_fields.setdefault('is_active', True)

        user = self.model(email=email, first_name=first_name, last_name=last_name, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, first_name, last_name, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, first_name, last_name, password, **extra_fields)




class User(AbstractBaseUser, PermissionsMixin):
    # Basic info
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(max_length=255, unique=True)
    phone = models.CharField(max_length=255, unique=True, blank=True, null=True)
    image = models.ImageField(upload_to='users/', blank=True, null=True)
    passport_id = models.CharField(max_length=100, blank=True, null=True, unique=True)
    # username = models.CharField(max_length=255, unique=True)

    payment_status = models.CharField(max_length=50, blank=True, null=True)
    attendance = models.CharField(max_length=50, blank=True, null=True)
    proctor = models.CharField(max_length=100, blank=True, null=True)
    listening_score = models.PositiveIntegerField(blank=True, null=True)
    gvr_score = models.PositiveIntegerField(blank=True, null=True)
    total_score = models.PositiveIntegerField(blank=True, null=True)
    writing_score = models.PositiveIntegerField(blank=True, null=True)
    cefr_level = models.CharField(max_length=3, blank=True, null=True)
    slate_status = models.CharField(max_length=50, blank=True, null=True)

    DECISION_CHOICES = [
        ('Pass', 'Pass'),
        ('Fail', 'Fail'),
        ('ESL Bridge', 'ESL Bridge'),
        ('ESL Full', 'ESL Full'),
        ('Conditional ESL Full', 'Conditional ESL Full'),
        ('Conditional Pass', 'Conditional Pass'),
    ]
    decision = models.CharField(
        max_length=50,
        choices=DECISION_CHOICES,
        blank=True,
        null=True,
        help_text="Final placement or exam result decision"
    )

    # -------------------- PAYMENT INTEGRATION --------------------
    PAYMENT_PROVIDER_CHOICES = [
        ('Payme', 'Payme'),
        ('Click', 'Click'),
        ('Xazna', 'Xazna'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Paid', 'Paid'),
        ('Failed', 'Failed'),
        ('Refunded', 'Refunded'),
    ]

    payment_provider = models.CharField(
        max_length=20,
        choices=PAYMENT_PROVIDER_CHOICES,
        blank=True,
        null=True,
        help_text="Platform through which payment was made"
    )

    transaction_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Unique transaction ID returned by provider"
    )

    amount_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Total amount paid by user"
    )

    payment_status_auto = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='Pending',
        help_text="Payment status synchronized from provider"
    )

    payment_date = models.DateTimeField(blank=True, null=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_bachelor = models.BooleanField(default=False)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"


_local_cache = {}
_local_lock = threading.Lock()


def getKey(key):
    try:
        return cache.get(key)
    except Exception as e:
        logger.warning(f"Cache get failed: {e}")
        with _local_lock:
            return _local_cache.get(key)


def setKey(key, value, timeout=None):
    try:
        cache.set(key, value, timeout)
    except Exception as e:
        logger.warning(f"Cache set failed: {e}")
        with _local_lock:
            _local_cache[key] = value
        if timeout:
            def _expire():
                import time
                time.sleep(timeout)
                with _local_lock:
                    _local_cache.pop(key, None)

            t = threading.Thread(target=_expire, daemon=True)
            t.start()
