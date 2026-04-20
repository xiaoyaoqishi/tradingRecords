from fastapi import APIRouter

from services import recycle_service

router = APIRouter(prefix="/api", tags=["recycle"])
router.add_api_route("/recycle/trades", recycle_service.list_recycle_trades, methods=["GET"])
router.add_api_route("/recycle/trades/{trade_id}/restore", recycle_service.restore_recycle_trade, methods=["POST"])
router.add_api_route("/recycle/trades/{trade_id}/purge", recycle_service.purge_recycle_trade, methods=["DELETE"])
router.add_api_route("/recycle/knowledge-items", recycle_service.list_recycle_knowledge_items, methods=["GET"])
router.add_api_route("/recycle/knowledge-items/{item_id}/restore", recycle_service.restore_recycle_knowledge_item, methods=["POST"])
router.add_api_route("/recycle/knowledge-items/{item_id}/purge", recycle_service.purge_recycle_knowledge_item, methods=["DELETE"])
router.add_api_route("/recycle/trade-brokers", recycle_service.list_recycle_trade_brokers, methods=["GET"])
router.add_api_route("/recycle/trade-brokers/{broker_id}/restore", recycle_service.restore_recycle_trade_broker, methods=["POST"])
router.add_api_route("/recycle/trade-brokers/{broker_id}/purge", recycle_service.purge_recycle_trade_broker, methods=["DELETE"])
router.add_api_route("/recycle/review-sessions", recycle_service.list_recycle_review_sessions, methods=["GET"])
router.add_api_route("/recycle/review-sessions/{review_session_id}/restore", recycle_service.restore_recycle_review_session, methods=["POST"])
router.add_api_route("/recycle/review-sessions/{review_session_id}/purge", recycle_service.purge_recycle_review_session, methods=["DELETE"])
router.add_api_route("/recycle/trade-plans", recycle_service.list_recycle_trade_plans, methods=["GET"])
router.add_api_route("/recycle/trade-plans/{trade_plan_id}/restore", recycle_service.restore_recycle_trade_plan, methods=["POST"])
router.add_api_route("/recycle/trade-plans/{trade_plan_id}/purge", recycle_service.purge_recycle_trade_plan, methods=["DELETE"])
router.add_api_route("/recycle/notes", recycle_service.list_recycle_notes, methods=["GET"])
router.add_api_route("/recycle/notes/{note_id}/restore", recycle_service.restore_note, methods=["POST"])
router.add_api_route("/recycle/notes/{note_id}/purge", recycle_service.purge_note, methods=["DELETE"])
router.add_api_route("/recycle/notes/clear", recycle_service.clear_recycle_notes, methods=["DELETE"])
