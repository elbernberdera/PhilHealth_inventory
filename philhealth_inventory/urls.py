
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    # Inventory app URLs - must come before Django admin to catch admin/dashboard/
    path('', include('inventory.urls')),
    # Django admin URLs
    path('admin/', admin.site.urls),
]
