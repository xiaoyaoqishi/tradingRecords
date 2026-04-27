from fastapi import APIRouter

from services import runtime

router = APIRouter(prefix="/api/knowledge-items", tags=["knowledge"])

router.get("")(runtime.list_knowledge_items)
router.post("")(runtime.create_knowledge_item)
router.get("/categories")(runtime.list_knowledge_item_categories)
router.post("/categories")(runtime.create_knowledge_item_category)
router.delete("/categories/{category_name}")(runtime.delete_knowledge_item_category)
router.get("/{item_id}")(runtime.get_knowledge_item)
router.put("/{item_id}")(runtime.update_knowledge_item)
router.delete("/{item_id}")(runtime.delete_knowledge_item)
