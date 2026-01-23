from django.db import models
from django.utils import timezone

# Create your models here.

class Category(models.Model):
    """Main Category model for inventory items"""
    name = models.CharField(max_length=100, unique=True, verbose_name="Category Name")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated At")
    is_active = models.BooleanField(default=True, verbose_name="Is Active")
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_categories',
        verbose_name="Created By"
    )
    
    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Supply(models.Model):
    """Supply/Inventory Item model"""
    # Basic Information
    item_code = models.CharField(max_length=100, unique=True, verbose_name="Item Code")
    description = models.TextField(verbose_name="Description")
    main_category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='supplies',
        verbose_name="Main Category"
    )
    sub_category = models.CharField(max_length=100, blank=True, null=True, verbose_name="Sub-Category")
    unit = models.CharField(max_length=50, verbose_name="Unit")
    
    # Transaction Information
    date = models.DateField(verbose_name="Date", help_text="Date when stock is added")
    transaction = models.CharField(max_length=100, verbose_name="Transaction", blank=True, null=True)
    requester_name = models.CharField(max_length=200, verbose_name="Name of Requester", blank=True, null=True)
    
    # Product Information
    expiration_date = models.DateField(
        verbose_name="Expiration Date",
        blank=True,
        null=True,
        help_text="Expiration date for perishable items (e.g., Service Perks)"
    )
    
    # Inventory Values
    opening_balance = models.IntegerField(
        default=0, 
        verbose_name="Opening Balance"
    )
    cost_per_item = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=0.00, 
        verbose_name="Cost per Item"
    )
    stock_in = models.IntegerField(
        default=0, 
        verbose_name="Stock-In (Replenish)"
    )
    running_count = models.IntegerField(
        default=0, 
        verbose_name="Running Count"
    )
    running_cost = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=0.00, 
        verbose_name="Running Cost"
    )
    total_released = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=0.00, 
        verbose_name="Total Released"
    )
    real_time_balance = models.IntegerField(
        default=0, 
        verbose_name="Real-Time Balance"
    )
    total_cost = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=0.00, 
        verbose_name="Total Cost"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated At")
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_supplies',
        verbose_name="Created By"
    )
    is_active = models.BooleanField(default=True, verbose_name="Is Active")
    
    class Meta:
        verbose_name = "Supply"
        verbose_name_plural = "Supplies"
        db_table = "supplies_tbl"
        # FIFO ordering: oldest first by date, then item_code, then created_at
        ordering = ['date', 'item_code', 'created_at']
        indexes = [
            models.Index(fields=['item_code']),
            models.Index(fields=['main_category']),
            models.Index(fields=['date']),
        ]
    
    def __str__(self):
        return f"{self.item_code} - {self.description[:50]}"
    
    def save(self, *args, **kwargs):
        # Auto-calculate values if not set (only for new records, not updates)
        # Convert to integers for whole number fields
        # Only set if the field is None or explicitly 0 AND this is a new record
        is_new = self.pk is None
        
        if is_new:
            # Set running_count to 0 by default for new supplies
            if self.running_count is None:
                self.running_count = 0
            
            # Calculate real_time_balance: opening_balance + stock_in
            if self.real_time_balance is None or self.real_time_balance == 0:
                self.real_time_balance = int(self.opening_balance + self.stock_in)
            
            # Set running_cost to 0 by default for new supplies
            if self.running_cost is None:
                self.running_cost = 0
            
            # Always calculate total_cost: opening_balance * cost_per_item
            self.total_cost = self.cost_per_item * self.opening_balance
        
        super().save(*args, **kwargs)


class RequestSupply(models.Model):
    """Request Supplies model for staff requests"""
    
    # Status choices
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('Out of Stocks', 'Out of Stocks'),
    ]
    
    # Stock In-Out choices
    STOCK_TYPE_CHOICES = [
        ('stock-in', 'Stock-In'),
        ('stock-out', 'Stock-Out'),
    ]
    
    # Transaction Information
    date = models.DateField(verbose_name="Date", help_text="Date of request")
    transaction_no = models.CharField(
        max_length=100, 
        unique=True, 
        verbose_name="Transaction No.",
        help_text="Transaction number (e.g., TR-0001)"
    )
    requester_name = models.CharField(
        max_length=200, 
        verbose_name="Name of Requester",
        help_text="Full name of the person requesting supplies"
    )
    
    # Item Information
    # Optional link to the actual Supply record; this \"connects\" the request
    # to the inventory item in supplies_tbl so we can update stock when approved.
    supply = models.ForeignKey(
        Supply,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='requests',
        verbose_name="Supply Item",
        help_text="Linked inventory item in supplies_tbl"
    )
    item_code = models.CharField(max_length=100, verbose_name="Item Code")
    description = models.TextField(verbose_name="Description")
    main_category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='requested_supplies',
        verbose_name="Main Category"
    )
    sub_category = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        verbose_name="Sub-Category"
    )
    unit = models.CharField(max_length=50, verbose_name="Unit")
    
    # Quantity and Cost
    quantity = models.IntegerField(
        default=1,
        verbose_name="Qty",
        help_text="Requested quantity"
    )
    cost_per_item = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00,
        verbose_name="Cost per Item"
    )
    total_cost = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00,
        verbose_name="Total Cost"
    )
    
    # Stock and Status
    stock_in_out = models.CharField(
        max_length=20,
        choices=STOCK_TYPE_CHOICES,
        default='stock-out',
        verbose_name="Stock In-Out"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name="Status"
    )
    conforme_by = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name="Conforme By",
        help_text="Name of person who approved/conformed the request"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated At")
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_request_supplies',
        verbose_name="Created By"
    )
    is_active = models.BooleanField(default=True, verbose_name="Is Active")
    
    class Meta:
        verbose_name = "Request Supply"
        verbose_name_plural = "Request Supplies"
        db_table = "Request_supplies_tbl"
        # FIFO ordering: oldest first by date, then item_code, then created_at
        ordering = ['date', 'item_code', 'created_at']
        indexes = [
            models.Index(fields=['transaction_no']),
            models.Index(fields=['date']),
            models.Index(fields=['status']),
            models.Index(fields=['requester_name']),
        ]
    
    def __str__(self):
        return f"{self.transaction_no} - {self.description[:50]}"
    
    def save(self, *args, **kwargs):
        # Auto-calculate total_cost if not set
        if not self.total_cost or self.total_cost == 0:
            self.total_cost = self.cost_per_item * self.quantity

        # Determine if status has changed so we can update stock accordingly
        old_status = None
        if self.pk:
            try:
                old = RequestSupply.objects.get(pk=self.pk)
                old_status = old.status
            except RequestSupply.DoesNotExist:
                old_status = None

        super().save(*args, **kwargs)

        # Only process stock changes if supply is linked
        if not self.supply:
            return

        qty = int(self.quantity or 0)
        if qty <= 0:
            return

        # Refresh supply from database to get latest balance values
        supply = self.supply
        supply.refresh_from_db()

        # Handle status changes
        if old_status != self.status:
            # If changing FROM approved to something else, restore the balance
            if old_status == 'approved' and self.status != 'approved':
                # Restore balance (add back the quantity)
                supply.real_time_balance = (supply.real_time_balance or 0) + qty
                supply.running_count = (supply.running_count or 0) + qty
                supply.total_released = max(0, (supply.total_released or 0) - qty)
            
            # If changing TO approved, deduct the balance
            elif self.status == 'approved' and old_status != 'approved':
                # Get current balance from database (already refreshed above)
                current_balance = supply.real_time_balance or 0
                current_running_count = supply.running_count or 0
                current_total_released = supply.total_released or 0
                
                # Deduct from running_count / real_time_balance and increase total_released
                supply.real_time_balance = max(0, current_balance - qty)
                supply.running_count = max(0, current_running_count - qty)
                supply.total_released = current_total_released + qty
            
            # Recalculate costs based on updated counts
            supply.running_cost = supply.cost_per_item * supply.running_count
            supply.total_cost = supply.cost_per_item * supply.stock_in
            supply.save()
