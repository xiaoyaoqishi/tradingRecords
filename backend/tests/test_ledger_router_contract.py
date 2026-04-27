import importlib

from routers.ledger import router
from services.ledger import analytics_service, category_service
from services.ledger.imports import pipeline


def test_ledger_router_import_does_not_depend_on_legacy_models():
    module = importlib.import_module("routers.ledger")
    assert getattr(module, "router", None) is not None


def test_ledger_router_public_handlers_have_backing_services():
    expected_pipeline_handlers = {
        "create_import_batch",
        "list_import_batches",
        "get_import_batch",
        "delete_import_batch",
        "parse_import_batch",
        "classify_import_batch",
        "dedupe_import_batch",
        "reprocess_import_batch",
        "list_review_rows",
        "get_review_insights",
        "review_bulk_set_category",
        "review_bulk_set_merchant",
        "review_bulk_confirm",
        "review_reclassify_pending",
        "review_generate_rule",
        "commit_import_batch",
        "list_merchants",
        "create_merchant",
        "update_merchant",
        "list_rules",
        "create_rule",
        "update_rule",
        "delete_rule",
    }
    for name in expected_pipeline_handlers:
        assert hasattr(pipeline, name), f"pipeline missing handler: {name}"

    for name in {
        "list_categories",
    }:
        assert hasattr(category_service, name), f"category_service missing handler: {name}"

    for name in {
        "get_summary",
        "get_category_breakdown",
        "get_platform_breakdown",
        "get_top_merchants",
        "get_monthly_trend",
        "get_unrecognized_breakdown",
    }:
        assert hasattr(analytics_service, name), f"analytics_service missing handler: {name}"


def test_ledger_router_public_routes_match_current_canonical_handlers():
    endpoint_names = {route.endpoint.__name__ for route in router.routes}
    assert endpoint_names == {
        "list_categories",
        "create_import_batch",
        "list_import_batches",
        "get_import_batch",
        "delete_import_batch",
        "parse_import_batch",
        "classify_import_batch",
        "dedupe_import_batch",
        "reprocess_import_batch",
        "list_review_rows",
        "get_review_insights",
        "review_bulk_set_category",
        "review_bulk_set_merchant",
        "review_bulk_confirm",
        "review_reclassify_pending",
        "review_generate_rule",
        "commit_import_batch",
        "list_merchants",
        "create_merchant",
        "update_merchant",
        "list_rules",
        "create_rule",
        "update_rule",
        "delete_rule",
        "analytics_summary",
        "analytics_category_breakdown",
        "analytics_platform_breakdown",
        "analytics_top_merchants",
        "analytics_monthly_trend",
        "analytics_unrecognized_breakdown",
    }


def test_ledger_router_does_not_expose_legacy_paths():
    paths = {route.path for route in router.routes}
    assert "/api/ledger/accounts" not in paths
    assert "/api/ledger/transactions" not in paths
    assert "/api/ledger/recurring" not in paths
