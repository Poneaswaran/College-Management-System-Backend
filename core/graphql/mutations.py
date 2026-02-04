import strawberry
from typing import Optional

from django.contrib.auth import authenticate, get_user_model
from django.db.models import Q

from .types import UserType

User = get_user_model()


# ==================================================
# INPUT TYPES
# ==================================================

@strawberry.input
class LoginInput:
    username: str  # email OR register number
    password: str


# ==================================================
# MUTATIONS
# ==================================================

@strawberry.type
class Mutation:

    @strawberry.mutation
    def login(self, data: LoginInput) -> Optional[UserType]:
        """
        Login using email OR register number
        """

        # Find user manually
        user = User.objects.filter(
            Q(email__iexact=data.username) |
            Q(register_number__iexact=data.username)
        ).first()

        if not user:
            raise Exception("Invalid credentials")

        if not user.check_password(data.password):
            raise Exception("Invalid credentials")

        if not user.is_active:
            raise Exception("User account is inactive")

        return user
