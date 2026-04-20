from fastapi import APIRouter

from services import notes_service

router = APIRouter(prefix="/api", tags=["todo"])
router.add_api_route("/todos", notes_service.list_todos, methods=["GET"])
router.add_api_route("/todos", notes_service.create_todo, methods=["POST"])
router.add_api_route("/todos/{todo_id}", notes_service.update_todo, methods=["PUT"])
router.add_api_route("/todos/{todo_id}", notes_service.delete_todo, methods=["DELETE"])
