from django.contrib.auth.base_user import BaseUserManager, AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin
from django.core.cache import cache
import threading
from django.db import models
import logging


class CustomUserManager(BaseUserManager):
    def create_user(self, email, first_name, last_name, passport_id=None, phone=None, is_bachelor=False, password=None):
        if not email:
            raise ValueError('User not found email')

        user = self.model(
            email=self.normalize_email(email),
            first_name=first_name,
            last_name=last_name,
            passport_id=passport_id,
            phone=phone,
            is_bachelor=is_bachelor,
            username=email,  # Set username to email for compatibility
        )
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, first_name, last_name, passport_id=None, phone=None, is_bachelor=False, password=None):
        user = self.create_user(email, first_name, last_name, passport_id, phone, is_bachelor, password)
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self._db)
        return user


class User(AbstractBaseUser, PermissionsMixin):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(max_length=255, unique=True)
    phone = models.CharField(max_length=255, unique=True, blank=True, null=True)
    image = models.ImageField(upload_to='users/', blank=True, null=True)

    passport_id = models.CharField(max_length=100, blank=True, null=True, unique=True)
    username = models.CharField(max_length=255, unique=True)
    is_bachelor = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = CustomUserManager()

    # Changed to use email for login instead of username
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name', 'passport_id']


# Local in-memory fallback cache used when the configured cache backend (e.g. Redis)
# is unavailable. This lets the app degrade gracefully instead of raising a
# ConnectionError during user registration or similar flows.
_local_cache = {}
_local_lock = threading.Lock()

logger = logging.getLogger(__name__)


def getKey(key):
    """Get a value from the primary cache, falling back to an in-memory store if
    the cache backend is unavailable.
    Returns the cached value or None if not present.
    """
    try:
        return cache.get(key)
    except Exception as e:
        # Cache backend (Redis) may be down/unreachable — fall back.
        logger.warning("Cache get failed for key %s, falling back to in-memory cache: %s", key, e)
        with _local_lock:
            return _local_cache.get(key)


def setKey(key, value, timeout=None):
    """Set a value in the primary cache, falling back to an in-memory store if
    the cache backend is unavailable.

    timeout: seconds (optional). When using the in-memory fallback we emulate a
    TTL by launching a background daemon thread to remove the key after timeout
    seconds. This is intentionally simple and suitable for development/local
    usage only.
    """
    try:
        cache.set(key, value, timeout)
    except Exception as e:
        logger.warning("Cache set failed for key %s, falling back to in-memory cache: %s", key, e)
        with _local_lock:
            _local_cache[key] = value

        # Emulate TTL for the fallback cache when a timeout is provided.
        if timeout:
            def _expire():
                import time
                time.sleep(timeout)
                with _local_lock:
                    _local_cache.pop(key, None)

            t = threading.Thread(target=_expire, daemon=True)
            t.start()


