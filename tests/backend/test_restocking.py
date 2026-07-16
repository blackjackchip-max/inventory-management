"""
Tests for restocking API endpoints (demand-forecast augmentation, recommendations,
and restock order creation/listing).
"""
import pytest

from mock_data import restock_orders


@pytest.fixture(autouse=True)
def clear_restock_orders():
    """restock_orders is a module-level mutable list shared across the whole
    process, so without clearing it, orders created in one test leak into the
    next. Clear before every test in this file."""
    restock_orders.clear()
    yield
    restock_orders.clear()


class TestDemandForecastAugmentation:
    """Test suite verifying the demand forecast catalog carries restocking data."""

    def test_demand_forecasts_include_unit_cost_and_lead_time(self, client):
        """Test that every demand forecast item has unit_cost and lead_time_days."""
        response = client.get("/api/demand")
        assert response.status_code == 200

        data = response.json()
        assert len(data) > 0

        for forecast in data:
            assert "unit_cost" in forecast
            assert "lead_time_days" in forecast
            assert isinstance(forecast["unit_cost"], (int, float))
            assert isinstance(forecast["lead_time_days"], int)
            assert forecast["unit_cost"] > 0
            assert forecast["lead_time_days"] > 0


class TestRestockRecommendations:
    """Test suite for the budget-constrained recommendation endpoint."""

    def test_recommendations_respect_budget(self, client):
        """Test that recommendations never exceed the requested budget."""
        for budget in [100, 500, 2000, 10000, 50000]:
            response = client.get(f"/api/restock-orders/recommendations?budget={budget}")
            assert response.status_code == 200

            data = response.json()
            assert data["total_cost"] <= budget
            calculated_total = sum(item["line_total"] for item in data["recommendations"])
            assert abs(data["total_cost"] - calculated_total) < 0.01

    def test_recommendations_skip_and_continue(self, client):
        """Test that a cheaper, lower-ranked item is still included when a
        higher-ranked item doesn't fit the budget (skip, don't stop)."""
        # FLT-405 has the largest demand gap (150 units @ $6.40 = $960) and ranks
        # first. GSK-203 also has a gap of 100 units @ $3.25 = $325 and ranks
        # second. A budget of $500 excludes FLT-405 but fits GSK-203 - proving
        # the walk continues past a miss instead of stopping there.
        response = client.get("/api/restock-orders/recommendations?budget=500")
        assert response.status_code == 200

        data = response.json()
        skus = [item["item_sku"] for item in data["recommendations"]]
        assert "FLT-405" not in skus
        assert "GSK-203" in skus

    def test_recommendations_exclude_non_positive_gap_items(self, client):
        """Test that items with decreasing/flat demand never appear, regardless
        of budget size."""
        response = client.get("/api/restock-orders/recommendations?budget=1000000")
        assert response.status_code == 200

        data = response.json()
        skus = [item["item_sku"] for item in data["recommendations"]]
        assert "MTR-304" not in skus

    def test_recommendations_zero_budget_returns_empty(self, client):
        """Test that a budget of zero recommends nothing."""
        response = client.get("/api/restock-orders/recommendations?budget=0")
        assert response.status_code == 200

        data = response.json()
        assert data["recommendations"] == []
        assert data["total_cost"] == 0

    def test_recommendations_negative_budget_returns_400(self, client):
        """Test that a negative budget is rejected."""
        response = client.get("/api/restock-orders/recommendations?budget=-100")
        assert response.status_code == 400


class TestRestockOrderCreation:
    """Test suite for submitting restock orders."""

    def test_create_restock_order_success(self, client):
        """Test that a valid restock order is created successfully."""
        payload = {
            "budget": 5000,
            "line_items": [{"item_sku": "GSK-203", "quantity": 100}]
        }
        response = client.post("/api/restock-orders", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert "id" in data
        assert data["status"] == "Submitted"
        assert data["total_cost"] == 325.0
        assert len(data["line_items"]) == 1
        assert data["line_items"][0]["item_name"] == "High-Temperature Gasket"
        assert data["max_lead_time_days"] == 7
        assert "expected_delivery_date" in data

    def test_create_restock_order_persists_and_appears_in_list(self, client):
        """Test that a created order is retrievable via the list endpoint."""
        payload = {
            "budget": 5000,
            "line_items": [{"item_sku": "GSK-203", "quantity": 100}]
        }
        create_response = client.post("/api/restock-orders", json=payload)
        new_id = create_response.json()["id"]

        list_response = client.get("/api/restock-orders")
        assert list_response.status_code == 200

        ids = [order["id"] for order in list_response.json()]
        assert new_id in ids

    def test_create_restock_order_empty_line_items_400(self, client):
        """Test that an order with no line items is rejected."""
        response = client.post("/api/restock-orders", json={"budget": 1000, "line_items": []})
        assert response.status_code == 400

    def test_create_restock_order_unknown_sku_404(self, client):
        """Test that an unknown SKU is rejected with 404."""
        payload = {
            "budget": 1000,
            "line_items": [{"item_sku": "NOT-A-REAL-SKU", "quantity": 10}]
        }
        response = client.post("/api/restock-orders", json=payload)
        assert response.status_code == 404

    def test_create_restock_order_exceeds_budget_400(self, client):
        """Test that an order costing more than the given budget is rejected."""
        payload = {
            "budget": 10,
            "line_items": [{"item_sku": "GSK-203", "quantity": 100}]
        }
        response = client.post("/api/restock-orders", json=payload)
        assert response.status_code == 400

    def test_create_restock_order_does_not_affect_existing_orders(self, client):
        """Test that submitting a restock order doesn't touch the regular
        customer orders list (proving it's a separate record type)."""
        before = client.get("/api/orders").json()

        payload = {
            "budget": 5000,
            "line_items": [{"item_sku": "GSK-203", "quantity": 100}]
        }
        client.post("/api/restock-orders", json=payload)

        after = client.get("/api/orders").json()
        assert len(before) == len(after)

    def test_expected_delivery_date_uses_max_lead_time_across_line_items(self, client):
        """Test that the delivery estimate uses the slowest line item's lead time."""
        # GSK-203 has a 7-day lead time, CTL-330 has a 20-day lead time.
        payload = {
            "budget": 10000,
            "line_items": [
                {"item_sku": "GSK-203", "quantity": 10},
                {"item_sku": "CTL-330", "quantity": 10}
            ]
        }
        response = client.post("/api/restock-orders", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["max_lead_time_days"] == 20


class TestRestockOrdersListEndpoint:
    """Test suite for the restock orders list endpoint."""

    def test_get_restock_orders_empty_initially(self, client):
        """Test that the list is empty when no orders have been created (the
        autouse fixture clears state before this test runs)."""
        response = client.get("/api/restock-orders")
        assert response.status_code == 200
        assert response.json() == []
