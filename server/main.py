from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta
import uuid
from mock_data import inventory_items, orders, demand_forecasts, backlog_items, spending_summary, monthly_spending, category_spending, recent_transactions, purchase_orders

app = FastAPI(title="Factory Inventory Management System")

# Quarter mapping for date filtering
QUARTER_MAP = {
    'Q1-2025': ['2025-01', '2025-02', '2025-03'],
    'Q2-2025': ['2025-04', '2025-05', '2025-06'],
    'Q3-2025': ['2025-07', '2025-08', '2025-09'],
    'Q4-2025': ['2025-10', '2025-11', '2025-12']
}

def filter_by_month(items: list, month: Optional[str]) -> list:
    """Filter items by month/quarter based on order_date field"""
    if not month or month == 'all':
        return items

    if month.startswith('Q'):
        # Handle quarters
        if month in QUARTER_MAP:
            months = QUARTER_MAP[month]
            return [item for item in items if any(m in item.get('order_date', '') for m in months)]
    else:
        # Direct month match
        return [item for item in items if month in item.get('order_date', '')]

    return items

def apply_filters(items: list, warehouse: Optional[str] = None, category: Optional[str] = None,
                 status: Optional[str] = None) -> list:
    """Apply common filters to a list of items"""
    filtered = items

    if warehouse and warehouse != 'all':
        filtered = [item for item in filtered if item.get('warehouse') == warehouse]

    if category and category != 'all':
        filtered = [item for item in filtered if item.get('category', '').lower() == category.lower()]

    if status and status != 'all':
        filtered = [item for item in filtered if item.get('status', '').lower() == status.lower()]

    return filtered

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data models
class InventoryItem(BaseModel):
    id: str
    sku: str
    name: str
    category: str
    warehouse: str
    quantity_on_hand: int
    reorder_point: int
    unit_cost: float
    location: str
    last_updated: str

class Order(BaseModel):
    id: str
    order_number: str
    customer: str
    items: List[dict]
    status: str
    order_date: str
    expected_delivery: str
    total_value: float
    actual_delivery: Optional[str] = None
    warehouse: Optional[str] = None
    category: Optional[str] = None

class DemandForecast(BaseModel):
    id: str
    item_sku: str
    item_name: str
    current_demand: int
    forecasted_demand: int
    trend: str
    period: str

class BacklogItem(BaseModel):
    id: str
    order_id: str
    item_sku: str
    item_name: str
    quantity_needed: int
    quantity_available: int
    days_delayed: int
    priority: str
    has_purchase_order: Optional[bool] = False

class PurchaseOrder(BaseModel):
    id: str
    backlog_item_id: str
    supplier_name: str
    quantity: int
    unit_cost: float
    expected_delivery_date: str
    status: str
    created_date: str
    notes: Optional[str] = None

class CreatePurchaseOrderRequest(BaseModel):
    backlog_item_id: str
    supplier_name: str
    quantity: int
    unit_cost: float
    expected_delivery_date: str
    notes: Optional[str] = None

class RestockingRecommendation(BaseModel):
    forecast_id: str
    item_sku: str
    item_name: str
    current_demand: int
    forecasted_demand: int
    trend: str
    recommended_quantity: int
    unit_cost: float
    total_cost: float
    priority: str
    lead_time_days: int

class RestockingOrderItem(BaseModel):
    item_sku: str
    item_name: str
    quantity: int
    unit_cost: float

class CreateRestockingOrderRequest(BaseModel):
    items: List[RestockingOrderItem]
    total_budget: float

class SubmittedOrder(BaseModel):
    id: str
    order_number: str
    items: List[dict]
    status: str
    order_date: str
    expected_delivery: str
    total_value: float
    lead_time_days: int

# In-memory store for submitted restocking orders
submitted_restocking_orders: List[dict] = []

# API endpoints
@app.get("/")
def root():
    return {"message": "Factory Inventory Management System API", "version": "1.0.0"}

@app.get("/api/inventory", response_model=List[InventoryItem])
def get_inventory(
    warehouse: Optional[str] = None,
    category: Optional[str] = None
):
    """Get all inventory items with optional filtering"""
    return apply_filters(inventory_items, warehouse, category)

@app.get("/api/inventory/{item_id}", response_model=InventoryItem)
def get_inventory_item(item_id: str):
    """Get a specific inventory item"""
    item = next((item for item in inventory_items if item["id"] == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item

@app.get("/api/orders", response_model=List[Order])
def get_orders(
    warehouse: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    month: Optional[str] = None
):
    """Get all orders with optional filtering"""
    filtered_orders = apply_filters(orders, warehouse, category, status)
    filtered_orders = filter_by_month(filtered_orders, month)
    return filtered_orders

@app.get("/api/orders/{order_id}", response_model=Order)
def get_order(order_id: str):
    """Get a specific order"""
    order = next((order for order in orders if order["id"] == order_id), None)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

@app.get("/api/demand", response_model=List[DemandForecast])
def get_demand_forecasts():
    """Get demand forecasts"""
    return demand_forecasts

@app.get("/api/backlog", response_model=List[BacklogItem])
def get_backlog():
    """Get backlog items with purchase order status"""
    # Add has_purchase_order flag to each backlog item
    result = []
    for item in backlog_items:
        item_dict = dict(item)
        # Check if this backlog item has a purchase order
        has_po = any(po["backlog_item_id"] == item["id"] for po in purchase_orders)
        item_dict["has_purchase_order"] = has_po
        result.append(item_dict)
    return result

@app.get("/api/dashboard/summary")
def get_dashboard_summary(
    warehouse: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    month: Optional[str] = None
):
    """Get summary statistics for dashboard with optional filtering"""
    # Filter inventory
    filtered_inventory = apply_filters(inventory_items, warehouse, category)

    # Filter orders
    filtered_orders = apply_filters(orders, warehouse, category, status)
    filtered_orders = filter_by_month(filtered_orders, month)

    total_inventory_value = sum(item["quantity_on_hand"] * item["unit_cost"] for item in filtered_inventory)
    low_stock_items = len([item for item in filtered_inventory if item["quantity_on_hand"] <= item["reorder_point"]])
    pending_orders = len([order for order in filtered_orders if order["status"] in ["Processing", "Backordered"]])
    total_backlog_items = len(backlog_items)

    return {
        "total_inventory_value": round(total_inventory_value, 2),
        "low_stock_items": low_stock_items,
        "pending_orders": pending_orders,
        "total_backlog_items": total_backlog_items,
        "total_orders_value": sum(order["total_value"] for order in filtered_orders)
    }

@app.get("/api/spending/summary")
def get_spending_summary():
    """Get spending summary statistics"""
    return spending_summary

@app.get("/api/spending/monthly")
def get_monthly_spending():
    """Get monthly spending breakdown"""
    return monthly_spending

@app.get("/api/spending/categories")
def get_category_spending():
    """Get spending by category"""
    return category_spending

@app.get("/api/spending/transactions")
def get_recent_transactions():
    """Get recent transactions"""
    return recent_transactions

@app.get("/api/reports/quarterly")
def get_quarterly_reports():
    """Get quarterly performance reports"""
    # Calculate quarterly statistics from orders
    quarters = {}

    for order in orders:
        order_date = order.get('order_date', '')
        # Determine quarter
        if '2025-01' in order_date or '2025-02' in order_date or '2025-03' in order_date:
            quarter = 'Q1-2025'
        elif '2025-04' in order_date or '2025-05' in order_date or '2025-06' in order_date:
            quarter = 'Q2-2025'
        elif '2025-07' in order_date or '2025-08' in order_date or '2025-09' in order_date:
            quarter = 'Q3-2025'
        elif '2025-10' in order_date or '2025-11' in order_date or '2025-12' in order_date:
            quarter = 'Q4-2025'
        else:
            continue

        if quarter not in quarters:
            quarters[quarter] = {
                'quarter': quarter,
                'total_orders': 0,
                'total_revenue': 0,
                'delivered_orders': 0,
                'avg_order_value': 0
            }

        quarters[quarter]['total_orders'] += 1
        quarters[quarter]['total_revenue'] += order.get('total_value', 0)
        if order.get('status') == 'Delivered':
            quarters[quarter]['delivered_orders'] += 1

    # Calculate averages and fulfillment rate
    result = []
    for q, data in quarters.items():
        if data['total_orders'] > 0:
            data['avg_order_value'] = round(data['total_revenue'] / data['total_orders'], 2)
            data['fulfillment_rate'] = round((data['delivered_orders'] / data['total_orders']) * 100, 1)
        result.append(data)

    # Sort by quarter
    result.sort(key=lambda x: x['quarter'])
    return result

@app.get("/api/reports/monthly-trends")
def get_monthly_trends():
    """Get month-over-month trends"""
    months = {}

    for order in orders:
        order_date = order.get('order_date', '')
        if not order_date:
            continue

        # Extract month (format: YYYY-MM-DD)
        month = order_date[:7]  # Gets YYYY-MM

        if month not in months:
            months[month] = {
                'month': month,
                'order_count': 0,
                'revenue': 0,
                'delivered_count': 0
            }

        months[month]['order_count'] += 1
        months[month]['revenue'] += order.get('total_value', 0)
        if order.get('status') == 'Delivered':
            months[month]['delivered_count'] += 1

    # Convert to list and sort
    result = list(months.values())
    result.sort(key=lambda x: x['month'])
    return result

@app.get("/api/restocking/recommendations")
def get_restocking_recommendations(budget: float = 50000.0):
    """Get restocking recommendations based on demand forecasts and available budget"""
    recommendations = []

    # Build a lookup from inventory by SKU for unit costs
    inventory_by_sku = {}
    for item in inventory_items:
        inventory_by_sku[item["sku"]] = item

    for forecast in demand_forecasts:
        sku = forecast["item_sku"]
        inv_item = inventory_by_sku.get(sku)

        if not inv_item:
            continue

        unit_cost = inv_item["unit_cost"]
        current_demand = forecast["current_demand"]
        forecasted_demand = forecast["forecasted_demand"]
        trend = forecast["trend"]

        # Calculate recommended restock quantity based on demand gap and trend
        demand_gap = forecasted_demand - current_demand
        quantity_on_hand = inv_item["quantity_on_hand"]
        reorder_point = inv_item["reorder_point"]

        # Base quantity: cover the forecasted demand minus what we have
        recommended_qty = max(0, forecasted_demand - quantity_on_hand)

        # Add safety stock buffer based on trend
        if trend == "increasing":
            recommended_qty = int(recommended_qty * 1.2)  # 20% buffer for increasing
        elif trend == "stable":
            recommended_qty = int(recommended_qty * 1.05)  # 5% buffer for stable

        # Skip items where we already have enough stock
        if recommended_qty <= 0:
            continue

        # Assign priority
        if trend == "increasing" and quantity_on_hand <= reorder_point:
            priority = "high"
        elif trend == "increasing" or quantity_on_hand <= reorder_point:
            priority = "medium"
        else:
            priority = "low"

        # Estimate lead time based on priority
        if priority == "high":
            lead_time = 5
        elif priority == "medium":
            lead_time = 10
        else:
            lead_time = 14

        total_cost = round(recommended_qty * unit_cost, 2)

        recommendations.append({
            "forecast_id": forecast["id"],
            "item_sku": sku,
            "item_name": forecast["item_name"],
            "current_demand": current_demand,
            "forecasted_demand": forecasted_demand,
            "trend": trend,
            "recommended_quantity": recommended_qty,
            "unit_cost": unit_cost,
            "total_cost": total_cost,
            "priority": priority,
            "lead_time_days": lead_time
        })

    # Sort by priority (high first), then by total_cost descending
    priority_order = {"high": 0, "medium": 1, "low": 2}
    recommendations.sort(key=lambda r: (priority_order.get(r["priority"], 3), -r["total_cost"]))

    # Filter recommendations to fit within budget using a greedy approach
    selected = []
    remaining_budget = budget
    for rec in recommendations:
        if rec["total_cost"] <= remaining_budget:
            selected.append(rec)
            remaining_budget -= rec["total_cost"]

    return {
        "recommendations": selected,
        "total_cost": round(budget - remaining_budget, 2),
        "remaining_budget": round(remaining_budget, 2),
        "budget": budget,
        "max_budget": round(sum(r["total_cost"] for r in recommendations), 2)
    }


@app.post("/api/restocking/orders")
def create_restocking_order(request: CreateRestockingOrderRequest):
    """Submit a restocking order based on recommendations"""
    if not request.items:
        raise HTTPException(status_code=400, detail="Order must contain at least one item")

    now = datetime.now()
    order_id = str(uuid.uuid4())[:8]
    order_number = f"RST-{now.strftime('%Y')}-{str(len(submitted_restocking_orders) + 1).zfill(4)}"

    # Calculate the max lead time among all items to set expected delivery
    max_lead_time = 14  # default
    inventory_by_sku = {item["sku"]: item for item in inventory_items}

    order_items = []
    total_value = 0.0
    for item in request.items:
        inv = inventory_by_sku.get(item.item_sku)
        unit_cost = inv["unit_cost"] if inv else item.unit_cost
        line_total = round(item.quantity * unit_cost, 2)
        total_value += line_total
        order_items.append({
            "sku": item.item_sku,
            "name": item.item_name,
            "quantity": item.quantity,
            "unit_price": unit_cost
        })

    # Determine lead time from the recommendations
    for forecast in demand_forecasts:
        matching_items = [i for i in request.items if i.item_sku == forecast["item_sku"]]
        if matching_items:
            inv = inventory_by_sku.get(forecast["item_sku"])
            if inv:
                if forecast["trend"] == "increasing" and inv["quantity_on_hand"] <= inv["reorder_point"]:
                    max_lead_time = max(max_lead_time, 5)
                elif forecast["trend"] == "increasing" or inv["quantity_on_hand"] <= inv["reorder_point"]:
                    max_lead_time = max(max_lead_time, 10)

    expected_delivery = (now + timedelta(days=max_lead_time)).strftime("%Y-%m-%dT%H:%M:%S")

    new_order = {
        "id": order_id,
        "order_number": order_number,
        "items": order_items,
        "status": "Processing",
        "order_date": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "expected_delivery": expected_delivery,
        "total_value": round(total_value, 2),
        "lead_time_days": max_lead_time
    }

    submitted_restocking_orders.append(new_order)

    return new_order


@app.get("/api/restocking/orders")
def get_restocking_orders():
    """Get all submitted restocking orders"""
    return submitted_restocking_orders


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
