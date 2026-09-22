# Inventory playbook — Aurora Supply
Source ID: inventory-playbook.md. Fictional revision 1.0.

Target inventory coverage is 21 days. Coverage below seven days triggers an alert
to the buyer. Read current stock from the inventory tool; this document does not
contain live stock balances.

A demand forecast includes its origin date, horizon, and model version. Showroom
data is synthetic and historical. Never describe it as real sales or imply that
the forecast origin is today's date.

Before recommending replenishment, check the SKU, stock, forecast, and supplier
lead time. Suggested quantity is max(0, estimated 21-day demand minus current stock),
rounded up to a whole unit. If a model or SKU is unavailable, report the missing
information instead of inventing values.
