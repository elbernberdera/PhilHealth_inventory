
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Inventory app URLs - must come before Django admin to catch admin/dashboard/
    path('', include('inventory.urls')),
    # Django admin URLs
    path('admin/', admin.site.urls),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
