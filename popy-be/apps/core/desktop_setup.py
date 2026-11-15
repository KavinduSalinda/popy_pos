"""First-run shop setup for the packaged desktop app.

The endpoint stays closed unless the Electron supervisor sets
POPY_ENABLE_DESKTOP_SETUP=1, and it only accepts connections from this PC.
"""

import os
import re

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.core.choices import Role
from apps.core.serializers import CamelCaseSerializer
from apps.settings.models import NotificationSettings
from apps.shops.models import Shop


def desktop_setup_enabled() -> bool:
    return os.environ.get("POPY_ENABLE_DESKTOP_SETUP") == "1"


def needs_desktop_setup() -> bool:
    if not desktop_setup_enabled():
        return False
    return not User.objects.exists()


def _is_loopback(request) -> bool:
    ip = request.META.get("REMOTE_ADDR", "")
    return ip in {"127.0.0.1", "::1"}


def _shop_code(name: str) -> str:
    base = re.sub(r"[^A-Za-z0-9]", "", name).upper()[:16] or "SHOP"
    code = base
    suffix = 2
    while Shop.objects.filter(code=code).exists():
        extra = str(suffix)
        code = f"{base[: 32 - len(extra)]}{extra}"
        suffix += 1
    return code


class DesktopSetupSerializer(CamelCaseSerializer):
    shop_name = serializers.CharField(max_length=120)
    admin_name = serializers.CharField(max_length=120)
    email = serializers.EmailField()
    password = serializers.CharField(min_length=8, max_length=128, write_only=True)


class DesktopSetupView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        if not desktop_setup_enabled():
            return Response({"message": "Setup is not available."}, status=status.HTTP_404_NOT_FOUND)
        if not _is_loopback(request):
            return Response(
                {"message": "Setup is only available on this computer."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = DesktopSetupSerializer(data=request.data)
        if not serializer.is_valid():
            messages = []
            for errs in serializer.errors.values():
                if isinstance(errs, list) and errs:
                    messages.append(str(errs[0]))
                else:
                    messages.append(str(errs))
            return Response(
                {"message": " ".join(messages) or "Check the form and try again."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        password = serializer.validated_data["password"]
        try:
            validate_password(password)
        except DjangoValidationError as exc:
            return Response({"message": " ".join(exc.messages)}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            if User.objects.select_for_update().exists():
                return Response(
                    {"message": "This POS is already set up."},
                    status=status.HTTP_409_CONFLICT,
                )
            shop = Shop.objects.create(
                name=serializer.validated_data["shop_name"].strip(),
                code=_shop_code(serializer.validated_data["shop_name"]),
            )
            NotificationSettings.load(shop)
            User.objects.create_user(
                email=serializer.validated_data["email"],
                password=password,
                name=serializer.validated_data["admin_name"].strip(),
                role=Role.SUPER_ADMIN,
                shop=shop,
                is_staff=True,
                is_superuser=True,
            )

        return Response(
            {"message": "Your shop is ready. Sign in to continue."},
            status=status.HTTP_201_CREATED,
        )
