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

from core.graphql.schema import schema


class CustomGraphQLView(GraphQLView):
    """Custom GraphQL view that returns 400 on errors"""
    
    def get_response(self, request, data, **kwargs):
        response = super().get_response(request, data, **kwargs)
        
        # If response has errors, change status to 400
        if hasattr(response, 'data'):
            import json
            try:
                response_data = json.loads(response.content)
                if 'errors' in response_data and response_data['errors']:
                    response.status_code = 400
            except (json.JSONDecodeError, AttributeError):
                pass
        
        return response


urlpatterns = [
    path('admin/', admin.site.urls),
    path("graphql/", csrf_exempt(CustomGraphQLView.as_view(schema=schema))),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
