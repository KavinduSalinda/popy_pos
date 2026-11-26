from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import HasPOSPermission
from apps.core.serializers import CamelCaseSerializer
from apps.core.shop_context import ShopScopedMixin
from apps.core.utils import dict_to_camel_case
from apps.insights.groq import InsightsError, answer_question, key_hint, resolve_api_key, write_summary
from apps.insights.models import ShopInsightSettings
from apps.insights.services import build_requirements


class InsightKeySerializer(CamelCaseSerializer):
    api_key = serializers.CharField(min_length=10, max_length=200, trim_whitespace=True)

    def validate_api_key(self, value):
        if any(char.isspace() for char in value):
            raise serializers.ValidationError("The API key cannot contain spaces.")
        return value


class HistoryTurnSerializer(CamelCaseSerializer):
    role = serializers.ChoiceField(choices=["user", "assistant"])
    content = serializers.CharField(max_length=8000, trim_whitespace=True)

    def validate_content(self, value):
        return value[:1000]


class AskSerializer(CamelCaseSerializer):
    question = serializers.CharField(max_length=500, trim_whitespace=True)
    history = HistoryTurnSerializer(many=True, required=False)

    def validate_question(self, value):
        if not value:
            raise serializers.ValidationError("Enter a question.")
        return value

    def validate_history(self, value):
        if len(value) > 6:
            raise serializers.ValidationError("Send at most the last six messages.")
        return value


def _error_response(exc: InsightsError) -> Response:
    return Response(
        {"message": exc.message, "statusCode": exc.status, "code": exc.code},
        status=exc.status,
    )


def _validation_message(errors) -> str:
    """First readable error. Skip empty items so a long chat history is not shown as {}."""
    if isinstance(errors, dict):
        for value in errors.values():
            message = _validation_message(value)
            if message:
                return message
        return ""
    if isinstance(errors, list):
        for item in errors:
            message = _validation_message(item)
            if message:
                return message
        return ""
    text = str(errors).strip()
    if text in {"", "{}", "[]"}:
        return ""
    return text


class InsightSettingsView(ShopScopedMixin, APIView):
    permission_classes = [IsAuthenticated, HasPOSPermission]
    required_permission = "REPORT_VIEW"

    def get(self, request):
        key = resolve_api_key(self.shop)
        return Response({"configured": bool(key), "keyHint": key_hint(key)})

    def put(self, request):
        serializer = InsightKeySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"message": _validation_message(serializer.errors) or "Check the form and try again.", "statusCode": 400},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ShopInsightSettings.objects.update_or_create(
            shop=self.shop,
            defaults={"groq_api_key": serializer.validated_data["api_key"]},
        )
        key = resolve_api_key(self.shop)
        return Response({"configured": True, "keyHint": key_hint(key)})


class RequirementsView(ShopScopedMixin, APIView):
    permission_classes = [IsAuthenticated, HasPOSPermission]
    required_permission = "REPORT_VIEW"

    def get(self, request):
        return Response(dict_to_camel_case(build_requirements(self.shop)))


class InsightSummaryView(ShopScopedMixin, APIView):
    permission_classes = [IsAuthenticated, HasPOSPermission]
    required_permission = "REPORT_VIEW"

    def post(self, request):
        try:
            payload = write_summary(self.shop)
        except InsightsError as exc:
            return _error_response(exc)
        return Response(payload)


class InsightAskView(ShopScopedMixin, APIView):
    permission_classes = [IsAuthenticated, HasPOSPermission]
    required_permission = "REPORT_VIEW"

    def post(self, request):
        serializer = AskSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"message": _validation_message(serializer.errors) or "Check the form and try again.", "statusCode": 400},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            answer = answer_question(
                self.shop,
                serializer.validated_data["question"],
                serializer.validated_data.get("history") or [],
            )
        except InsightsError as exc:
            return _error_response(exc)
        return Response({"answer": answer})
