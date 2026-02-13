"""
URL configuration for CMS project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from strawberry.django.views import GraphQLView
from django.http import JsonResponse
from django.conf import settings
from django.conf.urls.static import static
import json

from core.graphql.schema import schema


class CustomGraphQLView(GraphQLView):
    """Custom GraphQL view that returns proper HTTP status codes for errors"""
    
    def get_response(self, request, data, **kwargs):
        response = super().get_response(request, data, **kwargs)
        
        # Parse response to check for errors
        try:
            response_data = json.loads(response.content)
            
            # Check if there are errors in the response
            if 'errors' in response_data and response_data['errors']:
                errors = response_data['errors']
                
                # Determine status code based on error type
                status_code = 400  # Default to bad request
                
                for error in errors:
                    error_message = error.get('message', '').lower()
                    
                    # Authentication errors
                    if any(keyword in error_message for keyword in [
                        'authentication', 'not authenticated', 'permission denied',
                        'unauthorized', 'not authorized', 'token', 'invalid token'
                    ]):
                        status_code = 401
                        break
                    
                    # Authorization/Permission errors
                    elif any(keyword in error_message for keyword in [
                        'forbidden', 'not allowed', 'access denied',
                        'insufficient permissions', 'role'
                    ]):
                        status_code = 403
                        break
                    
                    # Not found errors
                    elif any(keyword in error_message for keyword in [
                        'not found', 'does not exist', 'no matching'
                    ]):
                        status_code = 404
                        break
                    
                    # Validation errors (keep as 400)
                    elif any(keyword in error_message for keyword in [
                        'invalid', 'required', 'validation', 'must be',
                        'cannot', 'expected'
                    ]):
                        status_code = 400
                        break
                
                response.status_code = status_code
                
        except (json.JSONDecodeError, AttributeError, KeyError):
            # If we can't parse the response, leave it as is
            pass
        
        return response


urlpatterns = [
    path('admin/', admin.site.urls),
    path("graphql/", csrf_exempt(CustomGraphQLView.as_view(schema=schema))),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
