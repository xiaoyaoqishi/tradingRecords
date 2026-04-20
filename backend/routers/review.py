from fastapi import APIRouter

from services import runtime

router = APIRouter(prefix="/api", tags=["review"])
router.add_api_route("/reviews", runtime.list_reviews, methods=["GET"])
router.add_api_route("/reviews", runtime.create_review, methods=["POST"])
router.add_api_route("/reviews/{review_id}", runtime.get_review, methods=["GET"])
router.add_api_route("/reviews/{review_id}", runtime.update_review, methods=["PUT"])
router.add_api_route("/reviews/{review_id}", runtime.delete_review, methods=["DELETE"])
router.add_api_route("/reviews/{review_id}/trade-links", runtime.upsert_review_trade_links, methods=["PUT"])
