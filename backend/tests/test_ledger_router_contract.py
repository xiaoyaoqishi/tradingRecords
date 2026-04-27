from services.ledger import analytics_service, category_service
from services.ledger.imports import pipeline


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
