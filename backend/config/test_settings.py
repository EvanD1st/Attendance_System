from .settings import *  # noqa: F403

# Fast password hashing is exclusively for isolated test databases.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
