from django.test import TestCase
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.conf import settings
from rest_framework import status
from rest_framework.test import APIClient
import jwt

from core.models import User, Role, Department, School

class LoginAPITestCase(TestCase):
    """
    Test suite for the REST API login endpoint.
    Exposes POST /api/core/auth/login/
    """
    def setUp(self):
        self.client = APIClient()
        self.url = reverse('login')  # Mapped as name='login' in core/urls.py

        # Create basic school, department, and roles
        self.school = School.objects.create(name="School of Engineering", code="SOE")
        self.department = Department.objects.create(
            school=self.school,
            name="Computer Science",
            code="CSE"
        )
        self.role = Role.objects.create(
            name="Faculty",
            code="FACULTY",
            department=self.department
        )

        # Create users
        self.user_email = "faculty@test.com"
        self.user_reg_num = "REG12345"
        self.password = "SecurePassword123"

        # User 1: Active user with email
        self.active_user_email = User.objects.create_user(
            email=self.user_email,
            password=self.password,
            role=self.role,
            department=self.department,
            is_active=True
        )

        # User 2: Active user with register number (no email)
        self.active_user_reg = User.objects.create_user(
            register_number=self.user_reg_num,
            password=self.password,
            role=self.role,
            department=self.department,
            is_active=True
        )

        # User 3: Inactive user
        self.inactive_user = User.objects.create_user(
            email="inactive@test.com",
            password=self.password,
            role=self.role,
            department=self.department,
            is_active=False
        )

    def test_login_success_with_email(self):
        """Test successful login using email."""
        payload = {
            "username": self.user_email,
            "password": self.password
        }
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify response structure
        data = response.data
        self.assertIn('access_token', data)
        self.assertIn('refresh_token', data)
        self.assertIn('user', data)
        self.assertIn('message', data)

        # Verify user details in response
        user_data = data['user']
        self.assertEqual(user_data['id'], self.active_user_email.id)
        self.assertEqual(user_data['email'], self.user_email)
        self.assertEqual(user_data['role'], 'FACULTY')
        self.assertEqual(user_data['department'], 'CSE')

        # Verify token payloads
        secret_key = settings.SECRET_KEY
        algorithm = getattr(settings, 'JWT_ALGORITHM', 'HS256')
        
        access_payload = jwt.decode(data['access_token'], secret_key, algorithms=[algorithm])
        self.assertEqual(access_payload['user_id'], self.active_user_email.id)
        self.assertEqual(access_payload['type'], 'access')

        refresh_payload = jwt.decode(data['refresh_token'], secret_key, algorithms=[algorithm])
        self.assertEqual(refresh_payload['user_id'], self.active_user_email.id)
        self.assertEqual(refresh_payload['type'], 'refresh')

    def test_login_success_with_register_number(self):
        """Test successful login using register number."""
        payload = {
            "username": self.user_reg_num,
            "password": self.password
        }
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.data
        self.assertIn('access_token', data)
        self.assertIn('refresh_token', data)
        self.assertEqual(data['user']['register_number'], self.user_reg_num)

    def test_login_success_case_insensitive(self):
        """Test login is case-insensitive for username/email."""
        payload = {
            "username": self.user_email.upper(),
            "password": self.password
        }
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        payload_reg = {
            "username": self.user_reg_num.lower(),
            "password": self.password
        }
        response_reg = self.client.post(self.url, payload_reg, format='json')
        self.assertEqual(response_reg.status_code, status.HTTP_200_OK)

    def test_login_invalid_password(self):
        """Test login fails with invalid password."""
        payload = {
            "username": self.user_email,
            "password": "WrongPassword"
        }
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data, {"error": "Invalid credentials"})

    def test_login_non_existent_user(self):
        """Test login fails for non-existent user."""
        payload = {
            "username": "nonexistent@test.com",
            "password": self.password
        }
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data, {"error": "Invalid credentials"})

    def test_login_inactive_user(self):
        """Test login fails for inactive user."""
        payload = {
            "username": "inactive@test.com",
            "password": self.password
        }
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {"error": "User account is inactive"})

    def test_login_missing_fields(self):
        """Test validation fails when required fields are missing."""
        # Missing password
        payload = {"username": self.user_email}
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)

        # Missing username
        payload = {"password": self.password}
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("username", response.data)
