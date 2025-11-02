import random
import logging
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from users.models import User, getKey, setKey

# Initialize logger
logger = logging.getLogger(__name__)


# ---------- Helper: Synchronous email sender with proper error handling ----------
def send_email_sync(subject, text_content, html_content, from_email, recipient):
    """
    Synchronous email sender with proper error handling and logging.
    Better for production servers where threading can be unreliable.
    """
    try:
        msg = EmailMultiAlternatives(subject, text_content, from_email, [recipient])
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=False)
        logger.info(f"✅ Email sent successfully to {recipient}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to send email to {recipient}: {str(e)}", exc_info=True)
        return False


# -------------------- REGISTER SERIALIZER --------------------
class UserRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(max_length=150, write_only=True)

    class Meta:
        model = User
        fields = (
            "first_name",
            "last_name",
            "email",
            "phone",
            "passport_id",
            "is_bachelor",
            "password",
        )

    def validate(self, attrs):
        activate_code = random.randint(100000, 999999)

        # Temporarily store user data in cache (not yet saved to DB)
        user_data = {
            "first_name": attrs["first_name"],
            "last_name": attrs["last_name"],
            "email": attrs["email"],
            "phone": attrs["phone"],
            "passport_id": attrs.get("passport_id"),
            "is_bachelor": attrs.get("is_bachelor", False),
            "password": attrs["password"],
            "is_active": False,
        }

        # Cache data for 15 minutes
        try:
            setKey(
                key=attrs["email"],
                value={"user": user_data, "activate_code": activate_code},
                timeout=900,
            )
            logger.info(f"📦 Cached registration data for {attrs['email']}")
        except Exception as e:
            logger.error(f"❌ Failed to cache data for {attrs['email']}: {e}")
            raise serializers.ValidationError({"error": "Failed to process registration. Please try again."})

        # Email setup
        subject = "Activate Your Account"
        try:
            html_content = render_to_string(
                "activation.html", {"user": user_data, "activate_code": activate_code}
            )
            text_content = strip_tags(html_content)
        except Exception as e:
            logger.error(f"❌ Failed to render email template: {e}")
            # Fallback to simple text email
            text_content = f"Your activation code is: {activate_code}"
            html_content = f"<p>Your activation code is: <strong>{activate_code}</strong></p>"

        from_email = f"WUT Team <{settings.EMAIL_HOST_USER}>"

        # Send email synchronously (more reliable on production)
        email_sent = send_email_sync(subject, text_content, html_content, from_email, attrs["email"])

        if not email_sent:
            logger.warning(f"⚠️ Email failed for {attrs['email']}, but activation code is: {activate_code}")
            # Still allow registration to proceed, but log the issue

        return attrs


# -------------------- ACTIVATION CODE CHECK --------------------
class CheckActivationCodeSerializer(serializers.Serializer):
    email = serializers.EmailField()
    activate_code = serializers.IntegerField(write_only=True)

    def validate(self, attrs):
        email = attrs.get("email")
        activate_code = attrs.get("activate_code")

        cache_data = getKey(key=email)
        if not cache_data:
            logger.warning(f"⚠️ No cached data found for {email}")
            raise serializers.ValidationError({"error": "Activation data not found or expired."})

        saved_code = cache_data.get("activate_code")
        if str(saved_code) != str(activate_code):
            logger.warning(f"⚠️ Invalid activation code for {email}")
            raise serializers.ValidationError({"error": "Invalid activation code."})

        logger.info(f"✅ Valid activation code for {email}")
        return attrs

    def create(self, validated_data):
        email = validated_data["email"]
        cache_data = getKey(key=email)
        user_data = cache_data.get("user")

        if not user_data:
            logger.error(f"❌ User data missing for {email}")
            raise serializers.ValidationError({"error": "User data missing or expired."})

        user_data["password"] = make_password(user_data["password"])
        user = User.objects.create(**user_data)
        user.is_active = True
        user.save()

        logger.info(f"✅ User created and activated: {email}")
        return user


# -------------------- RESET PASSWORD --------------------
class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField()
    activation_code = serializers.CharField()
    new_password = serializers.CharField()
    confirm_password = serializers.CharField()


# -------------------- USER SERIALIZER --------------------
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "first_name",
            "last_name",
            "email",
            "phone",
            "image",
            "passport_id",
            "is_bachelor",
        ]


# -------------------- USER MODEL SERIALIZER --------------------
class UserModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "phone")

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


# -------------------- USER SERVICE SERIALIZER --------------------
class UserServiceModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "first_name", "last_name", "email", "username", "image"]


# -------------------- SEND VERIFICATION CODE --------------------
class SendVerificationCodeSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def create(self, validated_data):
        email = validated_data["email"]
        verification_code = str(random.randint(100000, 999999))

        try:
            setKey(
                key=email,
                value={"activate_code": verification_code},
                timeout=600,
            )
            logger.info(f"📦 Cached verification code for {email}")
        except Exception as e:
            logger.error(f"❌ Failed to cache verification code: {e}")
            raise serializers.ValidationError({"error": "Failed to generate verification code."})

        subject = "Your Verification Code"
        try:
            html_content = render_to_string(
                "activation.html",
                {"activate_code": verification_code, "user": {"full_name": "User"}},
            )
            text_content = strip_tags(html_content)
        except Exception as e:
            logger.error(f"❌ Failed to render template: {e}")
            text_content = f"Your verification code is: {verification_code}"
            html_content = f"<p>Your verification code is: <strong>{verification_code}</strong></p>"

        from_email = f"WUT Team <{settings.EMAIL_HOST_USER}>"

        email_sent = send_email_sync(subject, text_content, html_content, from_email, email)

        if email_sent:
            logger.info(f"✅ Verification email sent to {email}")
        else:
            logger.error(f"❌ Email send failed for {email}. Code: {verification_code}")

        return {"email": email, "status": "Verification code sent"}


# -------------------- JWT LOGIN (EMAIL & PASSWORD) --------------------
class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = 'email'

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            logger.warning(f"⚠️ Login attempt with non-existent email: {email}")
            raise serializers.ValidationError({'email': 'User with this email does not exist.'})

        if not user.check_password(password):
            logger.warning(f"⚠️ Invalid password attempt for: {email}")
            raise serializers.ValidationError({'password': 'Incorrect password.'})

        if not user.is_active:
            logger.warning(f"⚠️ Login attempt for inactive account: {email}")
            raise serializers.ValidationError({'error': 'Account is not activated yet.'})

        refresh = RefreshToken.for_user(user)

        logger.info(f"✅ Successful login: {email}")

        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
            }
        }