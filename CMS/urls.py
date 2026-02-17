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
from .multipart_handler import parse_multipart_graphql_request

from core.graphql.schema import schema


class CustomGraphQLView(GraphQLView):
    """Custom GraphQL view that returns proper HTTP status codes for errors and handles multipart uploads"""
    
    def dispatch(self, request, *args, **kwargs):
        """Override dispatch to handle multipart requests early"""
        content_type = request.content_type or ""
        
        if "multipart/form-data" in content_type and request.method == "POST":
            try:
                # Parse multipart data
                parsed_data = parse_multipart_graphql_request(request)
                
                # Store uploaded files separately (they can't be JSON serialized)
                request._uploaded_files = {}
                
                # Replace file objects with None in parsed_data for JSON serialization
                def replace_files_with_none(obj, path=""):
                    if isinstance(obj, dict):
                        for key, value in list(obj.items()):
                            current_path = f"{path}.{key}" if path else key
                            if hasattr(value, 'read'):  # It's a file
                                request._uploaded_files[current_path] = value
                                obj[key] = None
                            elif isinstance(value, (dict, list)):
                                replace_files_with_none(value, current_path)
                    elif isinstance(obj, list):
                        for i, value in enumerate(obj):
                            current_path = f"{path}[{i}]"
                            if hasattr(value, 'read'):
                                request._uploaded_files[current_path] = value
                                obj[i] = None
                            elif isinstance(value, (dict, list)):
                                replace_files_with_none(value, current_path)
                
                replace_files_with_none(parsed_data)
                
                # Convert parsed data to JSON bytes
                json_data = json.dumps(parsed_data).encode('utf-8')
                
                # Replace request body with JSON
                from io import BytesIO
                request._body = json_data
                request._stream = BytesIO(json_data)
                
                # Force clear all content-type related caching
                for attr in ['_content_type', 'content_type']:
                    if hasattr(request, attr):
                        try:
                            delattr(request, attr)
                        except:
                            pass
                
                # Change content type to application/json so Strawberry accepts it
                request.META['CONTENT_TYPE'] = 'application/json'
                request.META['HTTP_CONTENT_TYPE'] = 'application/json'
                
                # Remove multipart boundary from content type
                if 'HTTP_CONTENT_TYPE' in request.META and 'multipart' in request.META['HTTP_CONTENT_TYPE']:
                    request.META['HTTP_CONTENT_TYPE'] = 'application/json'
                
                # Update content length
                request.META['CONTENT_LENGTH'] = str(len(json_data))
                
                # Create a wrapper to force content_type property
                original_content_type = type(request).content_type
                type(request).content_type = property(lambda self: 'application/json')
                
                # Store original property to restore later
                request._original_content_type_property = original_content_type
                
            except Exception as e:
                import traceback
                traceback.print_exc()
                return JsonResponse(
                    {"errors": [{"message": f"Invalid multipart request: {str(e)}"}]},
                    status=400
                )
        
        try:
            response = super().dispatch(request, *args, **kwargs)
            return response
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise
    
    def get_context(self, request, response=None):
        """Override to inject uploaded files back into context"""
        context = super().get_context(request, response)
        
        # If we have stored files, inject them back as an attribute
        if hasattr(request, '_uploaded_files'):
            context._uploaded_files = request._uploaded_files
        
        return context
    
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
