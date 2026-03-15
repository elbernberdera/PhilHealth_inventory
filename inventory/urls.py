
from django.contrib import admin
from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    path('dashboard/', views.dashboard_redirect, name='dashboard'),
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/profile/update/', views.update_profile, name='update_profile'),
    path('admin/users/', views.users_list, name='users'),
    path('admin/users/create/', views.user_create, name='user_create'),
    path('admin/users/<int:user_id>/edit/', views.user_edit, name='user_edit'),
    path('admin/users/<int:user_id>/delete/', views.user_delete, name='user_delete'),
    
    # Request Supply Module
    path('admin/supply/request-module/', views.request_supply_module, name='request_supply_module'),
    
    # Replenish/Add New Item
    path('admin/supply/replenish/', views.replenish_item, name='replenish_item'),
    
    # Requested Supplies
    path('admin/supply/requested/', views.requested_supplies, name='requested_supplies'),
    path('admin/supply/requested/history/', views.requested_supplies_history, name='requested_supplies_history'),
    
    # Category API endpoints
    path('api/categories/', views.category_list, name='category_list'),
    path('api/categories/create/', views.category_create, name='category_create'),
    path('api/categories/<int:category_id>/update/', views.category_update, name='category_update'),
    path('api/categories/<int:category_id>/delete/', views.category_delete, name='category_delete'),
    path('api/categories/<int:category_id>/delete-permanently/', views.category_delete_permanently, name='category_delete_permanently'),
    
    # Supply API endpoints
    path('api/supplies/', views.supply_list, name='supply_list'),
    path('api/supplies/create/', views.supply_create, name='supply_create'),
    path('api/supplies/generate-item-code/', views.generate_item_code, name='generate_item_code'),
    path('api/supplies/<int:supply_id>/', views.supply_detail, name='supply_detail'),
    path('api/supplies/<int:supply_id>/update/', views.supply_update, name='supply_update'),
    path('api/supplies/<int:supply_id>/add-stock/', views.supply_add_stock, name='supply_add_stock'),
    path('api/supplies/<int:supply_id>/delete/', views.supply_delete, name='supply_delete'),
    path('api/supplies/<int:supply_id>/restore/', views.supply_restore, name='supply_restore'),
    path('api/supplies/<int:supply_id>/delete-permanently/', views.supply_delete_permanently, name='supply_delete_permanently'),

    # Request Supply API (staff requests)
    path('api/request-supplies/', views.request_supply_list, name='request_supply_list'),
    path('api/request-supplies/create/', views.request_supply_create, name='request_supply_create'),
    path('api/request-supplies/<int:request_id>/update-status/', views.request_supply_update_status, name='request_supply_update_status'),





    # pang staff dashboard
    path('staff/dashboard/', views.staff_dashboard, name='staff_dashboard'),
    path('staff/profile/update/', views.staff_update_profile, name='staff_update_profile'),
    path('staff/supply/request/', views.staff_request_supplies, name='staff_request_supplies'),
]
