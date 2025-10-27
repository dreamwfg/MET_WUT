import json
import random

from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from rest_framework import status
from rest_framework.generics import GenericAPIView, CreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from root import settings
from users.models import User, getKey
from users.serializers import (UserRegisterSerializer, CheckActivationCodeSerializer, ResetPasswordSerializer,
                               ResetPasswordConfirmSerializer, UserSerializer, SendVerificationCodeSerializer)


class UserRegisterCreateAPIView(CreateAPIView):
    """
    API endpoint that allows users to be registered.

    Example request:
    """
    serializer_class = UserRegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class CheckActivationCodeGenericAPIView(GenericAPIView):
    """
    API endpoint that allows users to be checked activation code.

    Example request:
    """
    serializer_class = CheckActivationCodeSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.data

        # getKey may return None (expired/missing) or a JSON string depending on
        # how setKey was called elsewhere. Handle both cases robustly.
        cached = getKey(key=data['email'])
        if not cached:
            return Response({"detail": "Activation data not found or expired."}, status=status.HTTP_400_BAD_REQUEST)

        if isinstance(cached, str):
            try:
                cached = json.loads(cached)
            except Exception:
                return Response({"detail": "Activation data malformed."}, status=status.HTTP_400_BAD_REQUEST)

        # Expecting a dict with keys 'user' and 'activate_code'
        activate_code = cached.get('activate_code') if isinstance(cached, dict) else None
        user_data = cached.get('user') if isinstance(cached, dict) else None

        if activate_code is not None and activate_code == data['activate_code']:
            # If we have a serialized user object in cache, attempt to create/activate it.
            # If cache stored a full user instance, we may need different handling; here we
            # support the common pattern where `user` is a dict of user fields.
            if isinstance(user_data, dict):
                # Create the user record if it doesn't exist
                try:
                    user_obj = User.objects.get(email=user_data.get('email'))
                except User.DoesNotExist:
                    user_obj = User.objects.create_user(
                        email=user_data.get('email'),
                        first_name=user_data.get('first_name') or '',
                        last_name=user_data.get('last_name') or '',
                        passport_id=user_data.get('passport_id'),
                        phone=user_data.get('phone'),
                        is_bachelor=user_data.get('is_bachelor', False),
                        password=user_data.get('password')
                    )
            else:
                # If `user` is not a dict, assume it's an actual User instance
                user_obj = user_data if isinstance(user_data, User) else None

            if user_obj is None:
                return Response({"detail": "User data invalid or missing."}, status=status.HTTP_400_BAD_REQUEST)

            user_obj.is_active = True
            user_obj.save()
            refresh = RefreshToken.for_user(user_obj)

            return Response({
                "message": "Your email has been confirmed",
                "access_token": str(refresh.access_token),
                "refresh_token": str(refresh)
            }, status=status.HTTP_200_OK)

        return Response({"error": "Invalid activate code or email"}, status=status.HTTP_400_BAD_REQUEST)


class ResetPasswordView(CreateAPIView):
    """
    API endpoint that allows users to be reset password.

    Example request:
    """
    serializer_class = ResetPasswordSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                return Response({"detail": "User not found with this email."}, status=status.HTTP_400_BAD_REQUEST)

            activation_code = str(random.randint(100000, 999999))

            # Set new password
            user.set_password(activation_code)
            user.save()

            # Send email with activation code
            subject = "Password Reset Confirmation"
            html_content = render_to_string('forget_password.html', {'activation_code': activation_code})
            text_content = strip_tags(html_content)

            from_email = f"Aura Team <{settings.EMAIL_HOST_USER}>"
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=from_email,
                to=[email]
            )
            email.attach_alternative(html_content, "text/html")
            email.send()

            return Response({"detail": "Password reset code sent to your email."}, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ResetPasswordConfirmView(CreateAPIView):
    """
    API endpoint that allows users to be reset password confirm.

    Example request:
    """
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
                return Response({"detail": "User not found with this email."}, status=status.HTTP_400_BAD_REQUEST)

            if user.check_password(activation_code):
                if new_password == confirm_password:
                    user.set_password(new_password)
                    user.save()
                    return Response({"detail": "Password reset successfully."}, status=status.HTTP_200_OK)
                else:
                    return Response({"detail": "New password and confirm password do not match."},
                                    status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({"detail": "Invalid activation code."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserUpdateView(RetrieveUpdateDestroyAPIView):
    """
    API endpoint that allows users to be updated.

    Example request:
    """
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
                return Response({"detail": "User not found with this email."}, status=status.HTTP_400_BAD_REQUEST)

            activation_code = str(random.randint(100000, 999999))

            # Send email with activation code
            subject = "Activation Code"
            html_content = render_to_string('activation_payment.html', {'activation_code': activation_code})
            text_content = strip_tags(html_content)

            from_email = f"Aura Team <{settings.EMAIL_HOST_USER}>"
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=from_email,
                to=[email]
            )
            email.attach_alternative(html_content, "text/html")
            email.send()

            return Response({"detail": "Activation code sent to your email."}, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
