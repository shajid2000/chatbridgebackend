from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse

urlpatterns = [
    path('admin/', admin.site.urls),
    path('health/', lambda request: JsonResponse({'status': 'ok'})),
    path('api/', include('accounts.urls')),
    path('api/', include('integrations.urls')),
    path('api/', include('conversations.urls')),
]
