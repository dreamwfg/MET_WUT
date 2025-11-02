import random
import logging

from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from rest_framework import status
from rest_framework.generics import CreateAPIView, GenericAPIView
from rest_framework.generics import RetrieveUpdateDestroyAPIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from root import settings
from users.models import User, getKey
from users.serializers import (
    ResetPasswordSerializer,
    ResetPasswordConfirmSerializer,
    UserSerializer,
    SendVerificationCodeSerializer,
    EmailTokenObtainPairSerializer,
    UserRegisterSerializer,
    CheckActivationCodeSerializer,
)

# Initialize logger
logger = logging.getLogger(__name__)


# ---------- Helper: Synchronous email sender ----------
def send_email_with_logging(subject, text_content, html_content, from_email, recipient):
    """Send email synchronously with proper error handling"""
    try:
        msg = EmailMultiAlternatives(subject, text_content, from_email, [recipient])
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=False)
        logger.info(f"✅ Email sent successfully to {recipient}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to send email to {recipient}: {str(e)}", exc_info=True)
        return False


# -------------------- REGISTER VIEW --------------------
class UserRegisterView(GenericAPIView):
    serializer_class = UserRegisterSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # copy validated data but remove password before returning
        response_data = dict(serializer.validated_data)
        response_data.pop("password", None)

        logger.info(f"📧 Registration initiated for {response_data.get('email')}")

        return Response(
            {"detail": "Activation email sent successfully.", "data": response_data},
            status=status.HTTP_201_CREATED,
        )


# -------------------- ACTIVATION CODE CHECK VIEW --------------------
class CheckActivationCodeGenericAPIView(GenericAPIView):
    """Verify activation code and create active user."""
    serializer_class = CheckActivationCodeSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated = serializer.validated_data
        email = validated["email"]

        cache_data = getKey(key=email)
        if not cache_data:
            logger.warning(f"⚠️ Activation data expired for {email}")
            return Response({"error": "Activation data expired."}, status=status.HTTP_400_BAD_REQUEST)

        activate_code = cache_data.get("activate_code")
        user_data = cache_data.get("user")

        if str(activate_code) != str(validated["activate_code"]):
            logger.warning(f"⚠️ Invalid activation code for {email}")
            return Response({"error": "Invalid activation code."}, status=status.HTTP_400_BAD_REQUEST)

        # Create user
        try:
            user_obj = User.objects.create_user(
                email=user_data["email"],
                first_name=user_data["first_name"],
                last_name=user_data["last_name"],
                passport_id=user_data.get("passport_id"),
                phone=user_data.get("phone"),
                is_bachelor=user_data.get("is_bachelor", False),
                password=user_data["password"],
            )
            user_obj.is_active = True
            user_obj.save()

            logger.info(f"✅ User activated successfully: {email}")
        except Exception as e:
            logger.error(f"❌ Failed to create user {email}: {e}")
            return Response({"error": "Failed to activate account."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Issue JWT tokens
        refresh = RefreshToken.for_user(user_obj)

        return Response(
            {
                "message": "Your account has been activated successfully.",
                "access_token": str(refresh.access_token),
                "refresh_token": str(refresh),
            },
            status=status.HTTP_200_OK,
        )


class ResetPasswordView(CreateAPIView):
    """API endpoint that allows users to reset password."""
    serializer_class = ResetPasswordSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                logger.warning(f"⚠️ Password reset attempted for non-existent email: {email}")
                return Response({"detail": "User not found with this email."}, status=status.HTTP_400_BAD_REQUEST)

            activation_code = str(random.randint(100000, 999999))

            # Set new password
            user.set_password(activation_code)
            user.save()

            logger.info(f"🔐 Password reset initiated for {email}")

            # Send email with activation code
            subject = "Password Reset Confirmation"
            try:
                html_content = render_to_string('forget_password.html', {'activation_code': activation_code})
                text_content = strip_tags(html_content)
            except Exception as e:
                logger.error(f"❌ Template rendering failed: {e}")
                text_content = f"Your password reset code is: {activation_code}"
                html_content = f"<p>Your password reset code is: <strong>{activation_code}</strong></p>"

            from_email = f"WUT Team <{settings.EMAIL_HOST_USER}>"

            email_sent = send_email_with_logging(subject, text_content, html_content, from_email, email)

            if not email_sent:
                logger.error(f"❌ Password reset email failed for {email}. Code: {activation_code}")
                # Still return success to user for security reasons, but log the code

            return Response({"detail": "Password reset code sent to your email."}, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ResetPasswordConfirmView(CreateAPIView):
    """API endpoint that allows users to confirm password reset."""
    serializer_class = ResetPasswordConfirmSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            activation_code = serializer.validated_data['activation_code']
            new_password = serializer.validated_data['new_password']
            confirm_password = serializer.validated_data['confirm_password']

            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                logger.warning(f"⚠️ Password reset confirm for non-existent email: {email}")
                return Response({"detail": "User not found with this email."}, status=status.HTTP_400_BAD_REQUEST)

            if user.check_password(activation_code):
                if new_password == confirm_password:
                    user.set_password(new_password)
                    user.save()
                    logger.info(f"✅ Password reset successfully for {email}")
                    return Response({"detail": "Password reset successfully."}, status=status.HTTP_200_OK)
                else:
                    logger.warning(f"⚠️ Password mismatch for {email}")
                    return Response({"detail": "New password and confirm password do not match."},
                                    status=status.HTTP_400_BAD_REQUEST)
            else:
                logger.warning(f"⚠️ Invalid reset code for {email}")
                return Response({"detail": "Invalid activation code."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserUpdateView(RetrieveUpdateDestroyAPIView):
    """API endpoint that allows users to be updated."""
    serializer_class = UserSerializer
    queryset = User.objects.all()
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    http_method_names = ['get', 'put', 'patch']

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def get_object(self):
        return self.request.user


class SendVerificationCodeAPIView(CreateAPIView):
    serializer_class = SendVerificationCodeSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                logger.warning(f"⚠️ Verification code requested for non-existent email: {email}")
                return Response({"detail": "User not found with this email."}, status=status.HTTP_400_BAD_REQUEST)

            activation_code = str(random.randint(100000, 999999))

            # Send email with activation code
            subject = "Activation Code"
            try:
                html_content = render_to_string('activation.html', {'activation_code': activation_code})
                text_content = strip_tags(html_content)
            except Exception as e:
                logger.error(f"❌ Template rendering failed: {e}")
                text_content = f"Your activation code is: {activation_code}"
                html_content = f"<p>Your activation code is: <strong>{activation_code}</strong></p>"

            from_email = f"WUT Team <{settings.EMAIL_HOST_USER}>"

            email_sent = send_email_with_logging(subject, text_content, html_content, from_email, email)

            if email_sent:
                logger.info(f"✅ Verification code sent to {email}")
                return Response({"detail": "Activation code sent to your email."}, status=status.HTTP_200_OK)
            else:
                logger.error(f"❌ Failed to send verification code to {email}. Code: {activation_code}")
                return Response({"detail": "Failed to send email. Please try again."},
                                status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EmailTokenObtainPairView(TokenObtainPairView):
    """Use email instead of username for JWT token obtain."""
    serializer_class = EmailTokenObtainPairSerializer