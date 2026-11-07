from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models


def normalize_phone(raw):
    """Return a Kenyan number as +2547XXXXXXXX (or +2541XXXXXXXX). Returns '' if unusable."""
    digits = "".join(ch for ch in str(raw or "") if ch.isdigit())
    if digits.startswith("254"):
        digits = digits[3:]
    elif digits.startswith("0"):
        digits = digits[1:]
    if len(digits) != 9 or digits[0] not in "17":
        return ""
    return "+254" + digits


def mask_phone(phone):
    """+254712345678 -> 07•• ••• 678 (as shown in the Signal panel)."""
    if not phone:
        return ""
    local = "0" + phone[-9:] if phone.startswith("+254") else phone
    return f"{local[:2]}•• ••• {local[-3:]}"


def mask_phone_intl(phone):
    """+254712345678 -> +254 712 ••• 678 (web header)."""
    if not phone or not phone.startswith("+254"):
        return phone or ""
    return f"+254 {phone[4:7]} ••• {phone[-3:]}"


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, phone, password=None, **extra):
        phone = normalize_phone(phone) or phone
        user = self.model(phone=phone, **extra)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        return self.create_user(phone, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    phone = models.CharField(max_length=16, unique=True)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    subscriptions = models.ManyToManyField("transit.Route", blank=True, related_name="subscribers")

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.phone


class OtpCode(models.Model):
    """One login code. Only an HMAC of the code is stored."""

    phone = models.CharField(max_length=16, db_index=True)
    code_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    used = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.phone} (used={self.used})"
