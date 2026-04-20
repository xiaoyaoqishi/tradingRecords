from fastapi import APIRouter

from services import runtime

router = APIRouter(prefix="/api", tags=["knowledge"])
router.add_api_route("/knowledge-items", runtime.list_knowledge_items, methods=["GET"])
router.add_api_route("/knowledge-items/categories", runtime.list_knowledge_item_categories, methods=["GET"])
router.add_api_route("/knowledge-items", runtime.create_knowledge_item, methods=["POST"])
router.add_api_route("/knowledge-items/{item_id}", runtime.get_knowledge_item, methods=["GET"])
router.add_api_route("/knowledge-items/{item_id}", runtime.update_knowledge_item, methods=["PUT"])
router.add_api_route("/knowledge-items/{item_id}", runtime.delete_knowledge_item, methods=["DELETE"])
