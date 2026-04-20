from fastapi import APIRouter

from services import runtime

router = APIRouter(prefix="/api", tags=["trade_plans"])
router.add_api_route("/trade-plans", runtime.list_trade_plans, methods=["GET"])
router.add_api_route("/trade-plans", runtime.create_trade_plan, methods=["POST"])
router.add_api_route("/trade-plans/{trade_plan_id}", runtime.get_trade_plan, methods=["GET"])
router.add_api_route("/trade-plans/{trade_plan_id}", runtime.update_trade_plan, methods=["PUT"])
router.add_api_route("/trade-plans/{trade_plan_id}", runtime.delete_trade_plan, methods=["DELETE"])
router.add_api_route("/trade-plans/{trade_plan_id}/trade-links", runtime.upsert_trade_plan_trade_links, methods=["PUT"])
router.add_api_route("/trade-plans/{trade_plan_id}/review-session-links", runtime.upsert_trade_plan_review_session_links, methods=["PUT"])
router.add_api_route("/trade-plans/{trade_plan_id}/create-followup-review-session", runtime.create_followup_review_session_from_trade_plan, methods=["POST"])
