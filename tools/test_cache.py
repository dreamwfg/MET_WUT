import os
import sys
import time
from pathlib import Path

# Ensure the project root is on sys.path so `root.settings` can be imported
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Ensure Django settings are loaded
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'root.settings')
import django
django.setup()

from users.models import setKey, getKey

print('Setting key test:fallback -> {"a":1} with timeout=3')
setKey('test:fallback', {'a': 1}, timeout=3)
print('Immediate get:', getKey('test:fallback'))
print('Sleeping 4 seconds to allow expiry (if fallback TTL emulated)')
time.sleep(4)
print('Get after sleep:', getKey('test:fallback'))
