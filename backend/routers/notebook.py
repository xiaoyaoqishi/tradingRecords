from fastapi import APIRouter

from services import notes_service

router = APIRouter(prefix="/api", tags=["notebook"])
router.add_api_route("/notebooks", notes_service.list_notebooks, methods=["GET"])
router.add_api_route("/notebooks", notes_service.create_notebook, methods=["POST"])
router.add_api_route("/notebooks/{nb_id}", notes_service.update_notebook, methods=["PUT"])
router.add_api_route("/notebooks/{nb_id}", notes_service.delete_notebook, methods=["DELETE"])
