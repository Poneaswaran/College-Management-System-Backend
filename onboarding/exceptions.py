from rest_framework.exceptions import APIException


class OnboardingException(APIException):
    status_code = 400
    default_detail = "Onboarding operation failed"
    default_code = "onboarding_error"


class DuplicateUploadException(OnboardingException):
    default_detail = "This file appears to have already been uploaded"
    default_code = "duplicate_upload"


class BulkValidationException(OnboardingException):
    default_detail = "Bulk upload validation failed"
    default_code = "bulk_validation_error"
