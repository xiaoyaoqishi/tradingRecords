from fastapi import APIRouter

from services import recycle_service

router = APIRouter(prefix="/api/recycle", tags=["recycle"])

router.get("/trades")(recycle_service.list_recycle_trades)
router.post("/trades/{trade_id}/restore")(recycle_service.restore_recycle_trade)
router.delete("/trades/{trade_id}/purge")(recycle_service.purge_recycle_trade)
router.get("/knowledge-items")(recycle_service.list_recycle_knowledge_items)
router.post("/knowledge-items/{item_id}/restore")(recycle_service.restore_recycle_knowledge_item)
router.delete("/knowledge-items/{item_id}/purge")(recycle_service.purge_recycle_knowledge_item)
router.get("/trade-brokers")(recycle_service.list_recycle_trade_brokers)
router.post("/trade-brokers/{broker_id}/restore")(recycle_service.restore_recycle_trade_broker)
router.delete("/trade-brokers/{broker_id}/purge")(recycle_service.purge_recycle_trade_broker)
router.get("/review-sessions")(recycle_service.list_recycle_review_sessions)
router.post("/review-sessions/{review_session_id}/restore")(recycle_service.restore_recycle_review_session)
router.delete("/review-sessions/{review_session_id}/purge")(recycle_service.purge_recycle_review_session)
router.get("/trade-plans")(recycle_service.list_recycle_trade_plans)
router.post("/trade-plans/{trade_plan_id}/restore")(recycle_service.restore_recycle_trade_plan)
router.delete("/trade-plans/{trade_plan_id}/purge")(recycle_service.purge_recycle_trade_plan)
router.get("/notes")(recycle_service.list_recycle_notes)
router.post("/notes/{note_id}/restore")(recycle_service.restore_note)
router.delete("/notes/{note_id}/purge")(recycle_service.purge_note)
router.delete("/notes/clear")(recycle_service.clear_recycle_notes)
