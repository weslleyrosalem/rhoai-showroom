# Inventory playbook — Aurora Supply
Source ID: inventory-playbook.md. Fictional revision 1.1.

Target inventory coverage is 21 days. Coverage below seven days triggers an alert
to the buyer. Read current stock from the inventory tool; this document does not
contain live stock balances.

A demand forecast includes its origin date, horizon, and model version. Showroom
data is synthetic and historical. Never describe it as real sales or imply that
the forecast origin is today's date.

Before recommending replenishment, check the SKU, stock, forecast, and supplier
lead time. Target stock is max(reorder_point, ceil(forecast_7d_units * 21 / 7)).
The reorder point is a minimum target, even when the extrapolated demand is lower.
Suggested quantity is max(0, target_stock - current_stock). Target stock is the
inventory level before subtracting current stock; the suggested quantity is the
additional stock needed. Use the authoritative tool values without recomputing them. If a model or SKU is unavailable, report the missing
information instead of inventing values.
