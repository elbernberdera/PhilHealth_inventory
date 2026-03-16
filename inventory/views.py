from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.core.paginator import Paginator
import json

# Create your views here.

def home(request):
    """Home page view - redirects to login"""
    return redirect('login')

def get_dashboard_redirect(user):
    """Return the dashboard URL name for the given user (admin vs staff)."""
    if user.is_superuser:
        return 'admin_dashboard'
    if getattr(user, 'is_staff', False):
        return 'staff_dashboard'
    return 'admin_dashboard'


@login_required
def dashboard_redirect(request):
    """Redirect logged-in user to the correct dashboard (admin or staff)."""
    return redirect(get_dashboard_redirect(request.user))


def login(request):
    """Login view - authenticates user and redirects to dashboard."""
    # If user is already logged in, send to dashboard
    if request.user.is_authenticated:
        return redirect(get_dashboard_redirect(request.user))

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        if not username or not password:
            messages.error(request, 'Please enter both username and password.')
            return render(request, 'login.html')

        user = authenticate(request, username=username, password=password)
        if user is not None:
            auth_login(request, user)
            messages.success(request, 'Login successful!')
            return redirect(get_dashboard_redirect(user))
        messages.error(request, 'Invalid username or password.')

    return render(request, 'login.html')

@login_required
def admin_dashboard(request):
    """Admin dashboard view"""
    from django.contrib.auth.models import User
    from django.db.models import Sum, Count, Q
    from datetime import datetime, timedelta
    from .models import Supply, Category, RequestSupply
    
    # Get user count
    total_users = User.objects.count()
    
    # Get total active supplies count
    total_supplies = Supply.objects.filter(is_active=True).count()
    
    # Get out of stock supplies (real_time_balance <= 5) - matches Replenish page logic
    out_of_stock = Supply.objects.filter(
        is_active=True, 
        real_time_balance__lte=5
    ).count()
    
    # Get expiring supplies (within 30 days or already expired) - matches Replenish page logic
    today = timezone.now().date()
    date_threshold = today + timedelta(days=30)
    expiring_supplies = Supply.objects.filter(
        is_active=True,
        expiration_date__isnull=False,
        expiration_date__lte=date_threshold
    ).count()
    
    # Get pending requests count
    pending_requests = RequestSupply.objects.filter(
        is_active=True,
        status='pending'
    ).count()
    
    # Get low stock items (real_time_balance <= 5) - matches Replenish page "Out of Stock" logic
    low_stock_list = Supply.objects.filter(
        is_active=True,
        real_time_balance__lte=5
    ).order_by('real_time_balance')[:5]
    
    # Get recent transactions (last 5 approved requests)
    recent_transactions = RequestSupply.objects.filter(
        is_active=True,
        status='approved'
    ).order_by('-date', '-created_at')[:5]
    
    # Format recent transactions for display
    formatted_transactions = []
    for trans in recent_transactions:
        formatted_transactions.append({
            'date': trans.date,
            'item_name': trans.description[:30],
            'transaction_type': 'OUT' if trans.stock_in_out == 'stock-out' else 'IN',
            'quantity': trans.quantity
        })
    
    # Get recently added items (last 5 supplies)
    recent_items = Supply.objects.filter(
        is_active=True
    ).order_by('-created_at')[:5]
    
    # Format recent items for display
    formatted_recent_items = []
    for item in recent_items:
        formatted_recent_items.append({
            'name': item.description[:30],
            'category': item.main_category.name if item.main_category else 'N/A',
            'quantity': item.real_time_balance,
            'date_added': item.created_at
        })
    
    context = {
        # Statistics
        'total_supplies': total_supplies,
        'out_of_stock': out_of_stock,
        'expiring_supplies': expiring_supplies,
        'pending_requests': pending_requests,
        'total_users': total_users,
        
        # Lists
        'recent_transactions': formatted_transactions,
        'low_stock_list': low_stock_list,
        'recent_items': formatted_recent_items,
        
        # Chart data (for future implementation)
        'stock_by_category': [],
        'monthly_transactions': [],
    }
    return render(request, 'admin/admin_dashboard.html', context)

@login_required
def update_profile(request):
    """Update user profile view"""
    user = request.user
    
    if request.method == 'POST':
        # Update user information
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        # Email is read-only, so we don't update it from the form
        
        # Handle password change if provided
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        if new_password:
            if new_password != confirm_password:
                messages.error(request, 'Passwords do not match.')
                user.save()
                return render(request, 'admin/update_profile.html', {'user': user})
            
            # Validate password requirements
            has_length = len(new_password) >= 8
            has_uppercase = any(c.isupper() for c in new_password)
            has_lowercase = any(c.islower() for c in new_password)
            has_number = any(c.isdigit() for c in new_password)
            has_special = any(c in '!@#$%^&*()_+-=[]{};\':"\\|,.<>/?`~' for c in new_password)
            
            if not (has_length and has_uppercase and has_lowercase and has_number and has_special):
                messages.error(request, 'Password must meet all requirements: at least 8 characters, one uppercase, one lowercase, one number, and one special character.')
                user.save()
                return render(request, 'admin/update_profile.html', {'user': user})
            
            # Password meets all requirements
            user.set_password(new_password)
            messages.success(request, 'Password updated successfully!')
        
        # Save user changes
        user.save()
        messages.success(request, 'Profile updated successfully!')
        return redirect('update_profile')
    
    context = {
        'user': user,
    }
    return render(request, 'admin/update_profile.html', context)

@login_required
def users_list(request):
    """List all users"""
    from django.contrib.auth.models import User
    from django.core.paginator import Paginator
    from django.db.models import Q
    
    # Get search query
    search_query = request.GET.get('search', '').strip()
    
    # Start with all users, ordered by date_joined (oldest first, newest last)
    users = User.objects.all().order_by('date_joined', 'id')
    
    # Apply search filter if query exists
    if search_query:
        users = users.filter(
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(users, 5)  # Show 5 users per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'users': page_obj,
        'search_query': search_query,
        'total_users': users.count(),
    }
    return render(request, 'admin/users_list.html', context)

@login_required
def user_create(request):
    """Create new user"""
    from django.contrib.auth.models import User
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        role = request.POST.get('role')  # 'admin' or 'staff'
        is_active = request.POST.get('is_active') == 'on'
        
        # Validation
        if not username or not email or not password:
            messages.error(request, 'Username, email, and password are required.')
            context = {
                'form_type': 'create',
                'form_data': request.POST,
            }
            return render(request, 'admin/user_form.html', context)
        
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
            context = {
                'form_type': 'create',
                'form_data': request.POST,
            }
            return render(request, 'admin/user_form.html', context)
        
        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already exists.')
            context = {
                'form_type': 'create',
                'form_data': request.POST,
            }
            return render(request, 'admin/user_form.html', context)
        
        if password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            context = {
                'form_type': 'create',
                'form_data': request.POST,
            }
            return render(request, 'admin/user_form.html', context)
        
        # Validate password requirements
        has_length = len(password) >= 8
        has_uppercase = any(c.isupper() for c in password)
        has_lowercase = any(c.islower() for c in password)
        has_number = any(c.isdigit() for c in password)
        has_special = any(c in '!@#$%^&*()_+-=[]{};\':"\\|,.<>/?`~' for c in password)
        
        if not (has_length and has_uppercase and has_lowercase and has_number and has_special):
            messages.error(request, 'Password must meet all requirements: at least 8 characters, one uppercase, one lowercase, one number, and one special character.')
            context = {
                'form_type': 'create',
                'form_data': request.POST,
            }
            return render(request, 'admin/user_form.html', context)
        
        # Create user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            is_active=is_active
        )
        
        # Assign role based on selection
        if role == 'admin':
            user.is_superuser = True
            user.is_staff = True
        elif role == 'staff':
            user.is_superuser = False
            user.is_staff = True
        else:
            user.is_superuser = False
            user.is_staff = False
        
        user.save()
        messages.success(request, f'User "{username}" created successfully!')
        return redirect('users')
    
    context = {
        'form_type': 'create',
    }
    return render(request, 'admin/user_form.html', context)

@login_required
def user_edit(request, user_id):
    """Edit existing user"""
    from django.contrib.auth.models import User
    
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        messages.error(request, 'User not found.')
        return redirect('users')
    
    if request.method == 'POST':
        email = request.POST.get('email')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        role = request.POST.get('role')  # 'admin' or 'staff'
        is_active = request.POST.get('is_active') == 'on'
        
        # Update basic info
        user.email = email
        user.first_name = first_name
        user.last_name = last_name
        user.is_active = is_active
        
        # Update password if provided
        if password:
            if password != confirm_password:
                messages.error(request, 'Passwords do not match.')
                context = {
                    'form_type': 'edit',
                    'user': user,
                }
                return render(request, 'admin/user_form.html', context)
            
            # Validate password requirements
            has_length = len(password) >= 8
            has_uppercase = any(c.isupper() for c in password)
            has_lowercase = any(c.islower() for c in password)
            has_number = any(c.isdigit() for c in password)
            has_special = any(c in '!@#$%^&*()_+-=[]{};\':"\\|,.<>/?`~' for c in password)
            
            if not (has_length and has_uppercase and has_lowercase and has_number and has_special):
                messages.error(request, 'Password must meet all requirements: at least 8 characters, one uppercase, one lowercase, one number, and one special character.')
                context = {
                    'form_type': 'edit',
                    'user': user,
                }
                return render(request, 'admin/user_form.html', context)
            
            user.set_password(password)
        
        # Assign role based on selection
        if role == 'admin':
            user.is_superuser = True
            user.is_staff = True
        elif role == 'staff':
            user.is_superuser = False
            user.is_staff = True
        else:
            user.is_superuser = False
            user.is_staff = False
        
        user.save()
        messages.success(request, f'User "{user.username}" updated successfully!')
        return redirect('users')
    
    # Determine current role
    if user.is_superuser:
        current_role = 'admin'
    elif user.is_staff:
        current_role = 'staff'
    else:
        current_role = 'regular'
    
    context = {
        'form_type': 'edit',
        'user': user,
        'current_role': current_role,
    }
    return render(request, 'admin/user_form.html', context)

@login_required
def user_delete(request, user_id):
    """Delete user"""
    from django.contrib.auth.models import User
    
    try:
        user = User.objects.get(id=user_id)
        username = user.username
        
        # Prevent deleting yourself
        if user.id == request.user.id:
            messages.error(request, 'You cannot delete your own account.')
            return redirect('users')
        
        user.delete()
        messages.success(request, f'User "{username}" deleted successfully!')
    except User.DoesNotExist:
        messages.error(request, 'User not found.')
    
    return redirect('users_list')

def logout(request):
    """Logout view"""
    auth_logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('home')






# balhin sa taas kay pang admin pane
@login_required
def request_supply_module(request):
    """Request Supply Module view"""
    # Placeholder data - to be implemented with actual models
    context = {
        'page_title': 'Request Supply Module',
    }
    return render(request, 'admin/request_supply_module/request_supply_module.html', context)

@login_required
def replenish_item(request):
    """Replenish/Add New Item view"""
    from .models import Category, Supply
    from datetime import date, timedelta
    
    # Get all active categories for the dropdown
    categories = Category.objects.filter(is_active=True).order_by('name')
    # Get all active supplies - ordered by ID from newest to oldest (latest first)
    supplies = Supply.objects.filter(is_active=True).order_by('-id')
    # Get out of stock supplies (real_time_balance <= 5) - ordered by newest first
    out_of_stock_supplies = Supply.objects.filter(is_active=True, real_time_balance__lte=5).order_by('-id')
    # Get all deleted supplies (soft deleted) - ordered by newest to oldest (latest first)
    deleted_supplies = Supply.objects.filter(is_active=False).order_by('-id')
    
    # Get expiring supplies (within 30 days or already expired)
    today = date.today()
    date_threshold = today + timedelta(days=30)
    expiring_supplies = Supply.objects.filter(
        is_active=True,
        expiration_date__isnull=False,
        expiration_date__lte=date_threshold
    ).order_by('expiration_date', '-id')
    
    context = {
        'page_title': 'Replenish/Add New Item',
        'categories': categories,
        'supplies': supplies,
        'out_of_stock_supplies': out_of_stock_supplies,
        'deleted_supplies': deleted_supplies,
        'expiring_supplies': expiring_supplies,
    }
    return render(request, 'admin/Replenish/Replenish.html', context)

@login_required
def requested_supplies(request):
    """Requested Supplies view - FIFO (First In First Out) ordering"""
    from .models import RequestSupply
    
    # Get all active requested supplies - FIFO: oldest first by date, then item_code
    # This ensures oldest supplies are shown first for admin approval
    requests_qs = RequestSupply.objects.filter(
        is_active=True
    ).order_by('date', 'item_code', 'created_at')
    
    # Calculate counts for each status
    approved_count = requests_qs.filter(status='approved').count()
    pending_count = requests_qs.filter(status='pending').count()
    rejected_count = requests_qs.filter(status='rejected').count()
    out_of_stock_count = requests_qs.filter(status='Out of Stocks').count()
    
    context = {
        'page_title': 'Requested Supplies',
        'requests': requests_qs,
        'approved_count': approved_count,
        'pending_count': pending_count,
        'rejected_count': rejected_count,
        'out_of_stock_count': out_of_stock_count,
    }
    return render(request, 'admin/requested_supplies/requested_supplies.html', context)

@login_required
@require_http_methods(["POST"])
def request_supply_update_status(request, request_id):
    """Update the status of a RequestSupply"""
    try:
        from .models import RequestSupply
        from django.db import transaction
        
        request_supply = get_object_or_404(RequestSupply, id=request_id, is_active=True)
        
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST
        
        new_status = data.get('status', '').strip()
        conforme_by = data.get('conforme_by', '').strip()
        
        # Validate status
        valid_statuses = ['pending', 'approved', 'rejected', 'Out of Stocks']
        if new_status not in valid_statuses:
            return JsonResponse({
                'success': False,
                'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'
            }, status=400)
        
        # Use database transaction to ensure data consistency
        with transaction.atomic():
            # Store old status for comparison
            old_status = request_supply.status
            
            # Check balance before approving
            if new_status == 'approved' and old_status != 'approved':
                # Check if supply is linked and has enough balance
                if request_supply.supply:
                    required_qty = int(request_supply.quantity or 0)
                    available_balance = int(request_supply.supply.real_time_balance or 0)
                    
                    if required_qty > available_balance:
                        return JsonResponse({
                            'success': False,
                            'error': 'Insufficient balance. Available: ' + str(available_balance) + ', Required: ' + str(required_qty),
                            'insufficient_balance': True,
                            'available_balance': available_balance,
                            'required_quantity': required_qty
                        }, status=400)
                else:
                    # No supply linked - cannot approve
                    return JsonResponse({
                        'success': False,
                        'error': 'No supply item linked. Cannot approve request.',
                        'insufficient_balance': True
                    }, status=400)
            
            # Update status
            request_supply.status = new_status
            
            # Update conforme_by - prioritize provided value, then auto-populate for approved/rejected
            if conforme_by:
                request_supply.conforme_by = conforme_by
            elif new_status in ['approved', 'rejected']:
                # Auto-populate conforme_by from logged-in user for approved/rejected status
                conforme_name = f"{request.user.first_name} {request.user.last_name}".strip()
                if not conforme_name:
                    conforme_name = request.user.username
                request_supply.conforme_by = conforme_name
            
            # Save to database - this will trigger updated_at timestamp update and stock deduction if approved
            request_supply.save()
            
            # Refresh the supply object to get updated balance after save
            if request_supply.supply:
                request_supply.supply.refresh_from_db()
        
        # Return updated data including timestamp
        return JsonResponse({
            'success': True,
            'message': 'Status updated successfully!',
            'request': {
                'id': request_supply.id,
                'status': request_supply.status,
                'status_display': request_supply.get_status_display(),
                'conforme_by': request_supply.conforme_by or '',
                'updated_at': timezone.localtime(request_supply.updated_at).strftime('%m/%d/%Y %I:%M %p'),
            }
        })
    except RequestSupply.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Request not found.'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

# Category API Views
@login_required
@require_http_methods(["GET"])
def category_list(request):
    """Get list of all categories"""
    from .models import Category
    try:
        categories = Category.objects.filter(is_active=True).order_by('id')
        categories_data = [{
            'id': cat.id,
            'name': cat.name,
            'created_at': timezone.localtime(cat.created_at).strftime('%Y-%m-%d %H:%M:%S'),
        } for cat in categories]
        
        return JsonResponse({
            'success': True,
            'categories': categories_data
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
@require_http_methods(["POST"])
def category_create(request):
    """Create a new category"""
    from .models import Category
    
    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST
        
        name = data.get('name', '').strip()
        
        if not name:
            return JsonResponse({
                'success': False,
                'error': 'Category name is required.'
            }, status=400)
        
        # Check if category already exists
        if Category.objects.filter(name__iexact=name).exists():
            return JsonResponse({
                'success': False,
                'error': 'A category with this name already exists.'
            }, status=400)
        
        # Create category
        category = Category.objects.create(
            name=name,
            created_by=request.user
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Category created successfully!',
            'category': {
                'id': category.id,
                'name': category.name,
                'created_at': timezone.localtime(category.created_at).strftime('%Y-%m-%d %H:%M:%S'),
            }
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
@require_http_methods(["POST", "PUT"])
def category_update(request, category_id):
    """Update an existing category"""
    from .models import Category
    
    try:
        category = get_object_or_404(Category, id=category_id)
        
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST
        
        name = data.get('name', '').strip()
        
        if not name:
            return JsonResponse({
                'success': False,
                'error': 'Category name is required.'
            }, status=400)
        
        # Check if another category with the same name exists
        if Category.objects.filter(name__iexact=name).exclude(id=category_id).exists():
            return JsonResponse({
                'success': False,
                'error': 'A category with this name already exists.'
            }, status=400)
        
        # Update category
        category.name = name
        category.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Category updated successfully!',
            'category': {
                'id': category.id,
                'name': category.name,
                'updated_at': timezone.localtime(category.updated_at).strftime('%Y-%m-%d %H:%M:%S'),
            }
        })
    except Category.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Category not found.'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
@require_http_methods(["DELETE", "POST"])
def category_delete(request, category_id):
    """Delete a category (soft delete by setting is_active=False)"""
    from .models import Category
    
    try:
        category = get_object_or_404(Category, id=category_id)
        
        # Soft delete - set is_active to False
        category.is_active = False
        category.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Category deleted successfully!'
        })
    except Category.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Category not found.'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
def category_delete_permanently(request, category_id):
    """Permanently delete a category from database"""
    from .models import Category, Supply, RequestSupply
    from django.db import transaction
    
    try:
        category = get_object_or_404(Category, id=category_id)
        
        # Use transaction to ensure data consistency
        with transaction.atomic():
            # Check if there are related Supply records
            related_supplies = Supply.objects.filter(main_category=category)
            
            # Check if there are related RequestSupply records
            related_requests = RequestSupply.objects.filter(main_category=category)
            
            if related_supplies.exists() or related_requests.exists():
                # Set main_category to None for related records
                # This allows the Category to be deleted even with foreign key relationships
                related_supplies.update(main_category=None)
                related_requests.update(main_category=None)
            
            # Now perform the hard delete
            category.delete()
        
        return JsonResponse({
            'success': True,
            'message': 'Category permanently deleted from database!'
        })
    except Category.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Category not found.'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# Supply API endpoints
@login_required
@require_http_methods(["GET"])
def supply_list(request):
    """Get all supplies - FIFO (First In First Out) ordering"""
    try:
        from .models import Supply, Category
        # FIFO: Order by date (oldest first), then item_code, then created_at
        # This ensures oldest supplies are shown first when staff requests
        supplies = Supply.objects.filter(is_active=True).order_by('date', 'item_code', 'created_at')
        supplies_data = []
        for supply in supplies:
            supplies_data.append({
                'id': supply.id,
                'date': supply.date.strftime('%Y-%m-%d') if supply.date else '',
                'transaction': supply.transaction or '',
                'requester_name': supply.requester_name or '',
                'item_code': supply.item_code or '',
                'description': supply.description or '',
                'main_category': supply.main_category.id if supply.main_category else None,
                'main_category_name': supply.main_category.name if supply.main_category else '',
                'sub_category': supply.sub_category or '',
                'unit': supply.unit or '',
                'opening_balance': str(supply.opening_balance) if supply.opening_balance else '0',
                'cost_per_item': str(supply.cost_per_item) if supply.cost_per_item else '0.00',
                'stock_in': str(supply.stock_in) if supply.stock_in else '0',
                'running_count': str(supply.running_count) if supply.running_count else '0',
                'running_cost': str(supply.running_cost) if supply.running_cost else '0.00',
                'total_released': str(supply.total_released) if supply.total_released else '0',
                'real_time_balance': str(supply.real_time_balance) if supply.real_time_balance else '0',
                'total_cost': str(supply.total_cost) if supply.total_cost else '0.00',
                'created_at': timezone.localtime(supply.created_at).strftime('%Y-%m-%d %H:%M:%S') if supply.created_at else '',
            })
        return JsonResponse({
            'success': True,
            'supplies': supplies_data
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
def request_supply_create(request):
    """
    Create a new RequestSupply from the staff Request Supplies modal.
    - FIFO (First In First Out): Finds oldest supply by description (even if out of stock)
    - Links to a Supply record in supplies_tbl (via supply_id or description)
    - Copies item details from Supply
    - Uses the logged-in user's name as requester_name
    - Requests are allowed even when quantity exceeds available stock; admin handles approval.
    """
    try:
        from .models import RequestSupply, Supply
        from datetime import date as date_class
        from django.db.models import Q

        data = json.loads(request.body)

        supply_id = data.get('supply_id')
        description = data.get('description', '').strip()
        quantity = int(data.get('quantity') or 0)

        if quantity <= 0:
            return JsonResponse({
                'success': False,
                'error': 'Quantity must be greater than zero.',
                'out_of_stock': False
            }, status=400)

        supply = None
        
        # If supply_id provided, use it; otherwise find by description (FIFO)
        if supply_id:
            supply = Supply.objects.filter(id=supply_id, is_active=True).first()
        elif description:
            # FIFO: Find oldest supply with matching description (allow even with 0 stock so request can go to admin)
            supply = Supply.objects.filter(
                Q(description__iexact=description) | Q(description__icontains=description),
                is_active=True
            ).order_by('date', 'item_code', 'created_at').first()
        
        # Check if supply record exists (item must exist in catalog)
        if not supply:
            return JsonResponse({
                'success': False,
                'error': 'No supply found for this item. Please select an item from the search list.',
                'out_of_stock': False
            }, status=400)

        # Build requester name from logged-in user
        requester_name = f"{request.user.first_name} {request.user.last_name}".strip()
        if not requester_name:
            requester_name = request.user.username

        # Simple transaction number generator: TR-XXXX (incrementing)
        next_number = (RequestSupply.objects.count() or 0) + 1
        transaction_no = f"TR-{next_number:04d}"

        # Create request - item_code will be from supply if available, otherwise blank
        request_supply = RequestSupply(
            supply=supply,
            date=date_class.today(),
            transaction_no=transaction_no,
            requester_name=requester_name,
            item_code=supply.item_code if supply.item_code else '',  # Leave blank if no item_code
            description=supply.description,
            main_category=supply.main_category,
            sub_category=supply.sub_category,
            unit=supply.unit,
            quantity=quantity,
            cost_per_item=supply.cost_per_item,
            stock_in_out='stock-out',
            status='pending',
            created_by=request.user,
            is_active=True,
        )
        request_supply.save()

        return JsonResponse({
            'success': True,
            'message': 'Request created successfully!',
            'request': {
                'id': request_supply.id,
                'date': request_supply.date.strftime('%Y-%m-%d'),
                'transaction_no': request_supply.transaction_no,
                'requester_name': request_supply.requester_name,
                'item_code': request_supply.item_code or '',
                'description': request_supply.description,
                'main_category_name': request_supply.main_category.name if request_supply.main_category else '',
                'sub_category': request_supply.sub_category or '',
                'unit': request_supply.unit,
                'quantity': request_supply.quantity,
                'cost_per_item': str(request_supply.cost_per_item),
                'total_cost': str(request_supply.total_cost),
                'stock_in_out': request_supply.stock_in_out,
                'status': request_supply.status,
                'conforme_by': request_supply.conforme_by or '',
            }
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'out_of_stock': False
        }, status=500)

@login_required
@require_http_methods(["POST"])
def supply_create(request):
    """Create a new supply"""
    try:
        from .models import Supply, Category
        from datetime import date as date_class
        data = json.loads(request.body)
        
        # Get or create category
        main_category_id = data.get('main_category')
        if not main_category_id:
            return JsonResponse({
                'success': False,
                'error': 'Main category is required.'
            }, status=400)
        
        try:
            main_category = Category.objects.get(id=main_category_id, is_active=True)
        except Category.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Category not found.'
            }, status=404)
        
        # Handle date field - use today if not provided
        supply_date = data.get('date')
        if supply_date:
            try:
                # Parse date string (YYYY-MM-DD format)
                supply_date = date_class.fromisoformat(supply_date)
            except (ValueError, TypeError):
                supply_date = date_class.today()
        else:
            supply_date = date_class.today()
        
        # Handle expiration date field (optional - only for certain categories like Service Perks)
        expiration_date = data.get('expiration_date')
        if expiration_date:
            try:
                # Parse date string (YYYY-MM-DD format)
                expiration_date = date_class.fromisoformat(expiration_date)
            except (ValueError, TypeError):
                expiration_date = None
        else:
            expiration_date = None
        
        # Auto-populate requester_name from logged-in user
        requester_name = data.get('requester_name', '')
        if not requester_name:
            requester_name = f"{request.user.first_name} {request.user.last_name}".strip()
            if not requester_name:
                requester_name = request.user.username
        
        # Create supply
        # Note: running_count and running_cost are always 0 initially
        # They will be calculated when admin adds stock via "Add Stock" button
        supply = Supply(
            date=supply_date,
            transaction=data.get('transaction', ''),
            requester_name=requester_name,
            item_code=data.get('item_code', ''),
            description=data.get('description', ''),
            main_category=main_category,
            sub_category=data.get('sub_category', ''),
            unit=data.get('unit', ''),
            expiration_date=expiration_date,
            opening_balance=int(float(data.get('opening_balance', 0) or 0)),
            cost_per_item=float(data.get('cost_per_item', 0) or 0),
            stock_in=0,  # Default to 0 - will be updated via "Add Stock"
            running_count=0,  # Default to 0 - calculated when stock is added
            running_cost=0,  # Default to 0 - calculated when stock is added
            total_released=float(data.get('total_released', 0) or 0),
            real_time_balance=int(float(data.get('real_time_balance', 0) or 0)),
            total_cost=float(data.get('total_cost', 0) or 0),
            created_by=request.user,
            is_active=True
        )
        supply.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Supply created successfully!',
            'supply': {
                'id': supply.id,
                'item_code': supply.item_code,
            }
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["GET"])
def supply_detail(request, supply_id):
    """Get details of a single supply"""
    try:
        from .models import Supply
        supply = get_object_or_404(Supply, id=supply_id, is_active=True)
        
        return JsonResponse({
            'success': True,
            'supply': {
                'id': supply.id,
                'item_code': supply.item_code,
                'description': supply.description,
                'main_category': supply.main_category.id if supply.main_category else None,
                'main_category_name': supply.main_category.name if supply.main_category else '',
                'sub_category': supply.sub_category or '',
                'unit': supply.unit,
                'date': supply.date.isoformat() if supply.date else None,
                'transaction': supply.transaction or '',
                'requester_name': supply.requester_name or '',
                'expiration_date': supply.expiration_date.isoformat() if supply.expiration_date else None,
                'opening_balance': supply.opening_balance,
                'cost_per_item': str(supply.cost_per_item),
                'stock_in': supply.stock_in,
                'running_count': supply.running_count,
                'running_cost': str(supply.running_cost),
                'total_released': str(supply.total_released),
                'real_time_balance': supply.real_time_balance,
                'total_cost': str(supply.total_cost),
            }
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
def supply_update(request, supply_id):
    """Update an existing supply"""
    try:
        from .models import Supply, Category
        supply = get_object_or_404(Supply, id=supply_id, is_active=True)
        data = json.loads(request.body)
        
        # Update main category if provided
        main_category_id = data.get('main_category')
        if main_category_id:
            try:
                main_category = Category.objects.get(id=main_category_id, is_active=True)
                supply.main_category = main_category
            except Category.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Category not found.'
                }, status=404)
        
        # Update other fields
        if 'date' in data:
            from datetime import date as date_class
            supply_date = data.get('date')
            if supply_date:
                try:
                    # Parse date string (YYYY-MM-DD format)
                    supply.date = date_class.fromisoformat(supply_date)
                except (ValueError, TypeError):
                    # If date is invalid, keep current date
                    pass
        if 'expiration_date' in data:
            from datetime import date as date_class
            expiration_date = data.get('expiration_date')
            if expiration_date:
                try:
                    # Parse date string (YYYY-MM-DD format)
                    supply.expiration_date = date_class.fromisoformat(expiration_date)
                except (ValueError, TypeError):
                    # If date is invalid, set to None
                    supply.expiration_date = None
            else:
                supply.expiration_date = None
        if 'transaction' in data:
            supply.transaction = data.get('transaction', '')
        # Auto-populate requester_name from logged-in user if not provided
        if 'requester_name' in data:
            requester_name = data.get('requester_name', '')
            if not requester_name:
                requester_name = f"{request.user.first_name} {request.user.last_name}".strip()
                if not requester_name:
                    requester_name = request.user.username
            supply.requester_name = requester_name
        if 'item_code' in data:
            supply.item_code = data.get('item_code', '')
        if 'description' in data:
            supply.description = data.get('description', '')
        if 'sub_category' in data:
            supply.sub_category = data.get('sub_category', '')
        if 'unit' in data:
            supply.unit = data.get('unit', '')
        if 'opening_balance' in data:
            supply.opening_balance = int(float(data.get('opening_balance', 0) or 0))
        if 'cost_per_item' in data:
            supply.cost_per_item = float(data.get('cost_per_item', 0) or 0)
        if 'stock_in' in data:
            supply.stock_in = int(float(data.get('stock_in', 0) or 0))
        if 'running_count' in data:
            supply.running_count = int(float(data.get('running_count', 0) or 0))
        if 'running_cost' in data:
            supply.running_cost = float(data.get('running_cost', 0) or 0)
        if 'total_released' in data:
            supply.total_released = float(data.get('total_released', 0) or 0)
        if 'real_time_balance' in data:
            supply.real_time_balance = int(float(data.get('real_time_balance', 0) or 0))
        
        # Always recalculate total_cost: opening_balance * cost_per_item
        supply.total_cost = supply.cost_per_item * supply.opening_balance
        
        supply.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Supply updated successfully!'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
def supply_add_stock(request, supply_id):
    """
    Add stock to an existing supply.
    
    Formulas:
    - running_count = opening_balance + stock_in
    - running_cost = running_count * cost_per_item
    
    Only updates when admin adds stock via "Add Stock" button.
    """
    try:
        from .models import Supply
        supply = get_object_or_404(Supply, id=supply_id, is_active=True)
        data = json.loads(request.body)
        
        # Get the quantity to add
        quantity = int(data.get('quantity', 0))
        
        if quantity <= 0:
            return JsonResponse({
                'success': False,
                'error': 'Quantity must be greater than 0.'
            }, status=400)
        
        # Update stock_in (add to existing stock_in)
        supply.stock_in = (supply.stock_in or 0) + quantity
        
        # Calculate running_count using formula: opening_balance + stock_in
        supply.running_count = (supply.opening_balance or 0) + supply.stock_in
        
        # Update real_time_balance (add quantity)
        supply.real_time_balance = (supply.real_time_balance or 0) + quantity
        
        # Calculate running_cost using formula: running_count * cost_per_item
        supply.running_cost = supply.running_count * supply.cost_per_item
        
        supply.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Successfully added {quantity} units to stock!',
            'supply': {
                'stock_in': supply.stock_in,
                'running_count': supply.running_count,
                'real_time_balance': supply.real_time_balance,
                'running_cost': str(supply.running_cost)
            }
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
def supply_delete(request, supply_id):
    """Delete (soft delete) a supply"""
    try:
        from .models import Supply
        supply = get_object_or_404(Supply, id=supply_id, is_active=True)
        supply.is_active = False
        supply.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Supply deleted successfully!'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
def supply_restore(request, supply_id):
    """Restore a soft-deleted supply"""
    try:
        from .models import Supply
        supply = get_object_or_404(Supply, id=supply_id, is_active=False)
        supply.is_active = True
        supply.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Supply restored successfully!'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["GET"])
def generate_item_code(request):
    """Generate the next item code in format ITMmmddyy00000 with continuous sequential numbering"""
    try:
        from .models import Supply
        from datetime import date
        
        # Get today's date
        today = date.today()
        
        # Format: ITMmmddyy00000
        # mm = month (2 digits), dd = day (2 digits), yy = year (2 digits)
        date_prefix = f"ITM{today.strftime('%m%d%y')}"
        
        # Find ALL existing item codes that start with "ITM" (not just today's)
        # This ensures continuous numbering across different dates
        existing_codes = Supply.objects.filter(
            item_code__startswith="ITM"
        ).values_list('item_code', flat=True)
        
        # Extract the numeric part and find the maximum across ALL dates
        max_number = 0
        for code in existing_codes:
            try:
                # Extract the 5-digit number at the end (last 5 characters)
                number_part = code[-5:]
                number = int(number_part)
                if number > max_number:
                    max_number = number
            except (ValueError, IndexError):
                # Skip invalid codes
                continue
        
        # Increment for the next item code (continues from the highest number found)
        next_number = max_number + 1
        
        # Format the new item code: ITMmmddyy00000 (today's date + continuous sequential number)
        new_item_code = f"{date_prefix}{next_number:05d}"
        
        return JsonResponse({
            'success': True,
            'item_code': new_item_code
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
def supply_delete_permanently(request, supply_id):
    """Permanently delete a supply from database"""
    try:
        from .models import Supply, RequestSupply
        from django.db.models import ProtectedError
        from django.db import transaction
        
        supply = get_object_or_404(Supply, id=supply_id, is_active=False)
        
        # Use transaction to ensure data consistency
        with transaction.atomic():
            # Check if there are related RequestSupply records
            related_requests = RequestSupply.objects.filter(supply=supply)
            
            if related_requests.exists():
                # Break the foreign key relationship by setting supply to None
                # This allows the Supply to be deleted even with PROTECT constraint
                related_requests.update(supply=None)
            
            # Now perform the hard delete
            supply.delete()  # Hard delete - removes from database
        
        return JsonResponse({
            'success': True,
            'message': 'Supply permanently deleted from database!'
        })
    except ProtectedError as e:
        # Handle case where deletion is still protected (shouldn't happen after setting supply=None)
        return JsonResponse({
            'success': False,
            'error': 'Cannot delete this supply because it has related request records. Please delete or update related requests first.'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)












# pang staff dashboard
@login_required
def staff_dashboard(request):
    """Staff dashboard view"""
    from django.contrib.auth.models import User
    from django.db.models import Sum, Count, Q
    from datetime import datetime, timedelta
    
    # Placeholder data - replace with actual model queries when models are created
    context = {
        # Statistics
        'total_items': 0,  # Total inventory items
        'total_categories': 0,  # Total categories
        'low_stock_items': 0,  # Items below threshold
        'total_value': 0,  # Total inventory value
        'recent_transactions': [],  # Recent stock movements
        'low_stock_list': [],  # List of low stock items
        'recent_items': [],  # Recently added items
        
        # Chart data (for future implementation)
        'stock_by_category': [],
        'monthly_transactions': [],
    }
    return render(request, 'staff/staff_dashboard.html', context)

@login_required
def staff_request_supplies(request):
    """Staff Request Supplies view"""
    context = {
        'page_title': 'Request Supplies',
    }
    return render(request, 'staff/request_supplies/request_supplies.html', context)


@login_required
@require_http_methods(["GET"])
def request_supply_list(request):
    """Get paginated request supplies - for admin: all requests, for staff: only their requests"""
    try:
        from .models import RequestSupply
        # For admin users, show all requests; for staff, show only their requests
        if request.user.is_staff or request.user.is_superuser:
            qs = RequestSupply.objects.filter(is_active=True).order_by('-created_at', '-date')
        else:
            qs = RequestSupply.objects.filter(
                created_by=request.user,
                is_active=True
            ).order_by('-created_at', '-date')

        # Filter by status if provided
        status_filter = request.GET.get('status', '').strip().lower()
        if status_filter == 'approved':
            qs = qs.filter(status='approved')
        elif status_filter == 'pending':
            qs = qs.filter(status='pending')
        elif status_filter == 'rejected':
            qs = qs.filter(status='rejected')

        # Pagination (10 per page by default)
        page = int(request.GET.get('page', 1) or 1)
        page_size = 10
        paginator = Paginator(qs, page_size)
        page_obj = paginator.get_page(page)
        
        requests_data = []
        for req in page_obj.object_list:
            requests_data.append({
                'id': req.id,
                'date': req.date.strftime('%m/%d/%Y') if req.date else '',
                'transaction_no': req.transaction_no or '',
                'requester_name': req.requester_name or '',
                'item_code': req.item_code or '',
                'description': req.description or '',
                'main_category': req.main_category.name if req.main_category else '',
                'sub_category': req.sub_category or '',
                'unit': req.unit or '',
                'quantity': req.quantity,
                'status': req.get_status_display(),
                'status_value': req.status,
                'conforme_by': req.conforme_by or '',
            })
        
        return JsonResponse({
            'success': True,
            'requests': requests_data,
            'pagination': {
                'current_page': page_obj.number,
                'total_pages': paginator.num_pages,
                'total_items': paginator.count,
                'page_size': page_size,
                'has_previous': page_obj.has_previous(),
                'has_next': page_obj.has_next(),
            }
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
def staff_update_profile(request):
    """Staff update profile view"""
    user = request.user
    
    if request.method == 'POST':
        # Update user information
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        # Email is read-only, so we don't update it from the form
        
        # Handle password change if provided
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        if new_password:
            if new_password != confirm_password:
                messages.error(request, 'Passwords do not match.')
                user.save()
                return render(request, 'staff/update_profile.html', {'user': user})
            
            # Validate password requirements
            has_length = len(new_password) >= 8
            has_uppercase = any(c.isupper() for c in new_password)
            has_lowercase = any(c.islower() for c in new_password)
            has_number = any(c.isdigit() for c in new_password)
            has_special = any(c in '!@#$%^&*()_+-=[]{};\':"\\|,.<>/?`~' for c in new_password)
            
            if not (has_length and has_uppercase and has_lowercase and has_number and has_special):
                messages.error(request, 'Password must meet all requirements: at least 8 characters, one uppercase, one lowercase, one number, and one special character.')
                user.save()
                return render(request, 'staff/update_profile.html', {'user': user})
            
            # Password meets all requirements
            user.set_password(new_password)
            messages.success(request, 'Password updated successfully!')
        
        # Save user changes
        user.save()
        messages.success(request, 'Profile updated successfully!')
        return redirect('staff_update_profile')
    
    context = {
        'user': user,
    }
    return render(request, 'staff/update_profile.html', context)


