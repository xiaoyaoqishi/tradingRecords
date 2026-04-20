from fastapi import APIRouter

from services import runtime

router = APIRouter(prefix="/api", tags=["review_sessions"])
router.add_api_route("/review-sessions", runtime.list_review_sessions, methods=["GET"])
router.add_api_route("/review-sessions", runtime.create_review_session, methods=["POST"])
router.add_api_route("/review-sessions/create-from-selection", runtime.create_review_session_from_selection, methods=["POST"])
router.add_api_route("/review-sessions/{review_session_id}", runtime.get_review_session, methods=["GET"])
router.add_api_route("/review-sessions/{review_session_id}", runtime.update_review_session, methods=["PUT"])
router.add_api_route("/review-sessions/{review_session_id}", runtime.delete_review_session, methods=["DELETE"])
router.add_api_route("/review-sessions/{review_session_id}/trade-links", runtime.upsert_review_session_trade_links, methods=["PUT"])
