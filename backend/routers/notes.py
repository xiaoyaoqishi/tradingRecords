from fastapi import APIRouter

from services import notes_service

router = APIRouter(prefix="/api", tags=["notes"])
router.add_api_route("/notes", notes_service.list_notes, methods=["GET"])
router.add_api_route("/notes/stats", notes_service.note_stats, methods=["GET"])
router.add_api_route("/notes/history-today", notes_service.history_today, methods=["GET"])
router.add_api_route("/notes/diary-tree", notes_service.diary_tree, methods=["GET"])
router.add_api_route("/notes/search", notes_service.search_notes, methods=["GET"])
router.add_api_route("/notes/resolve-link", notes_service.resolve_note_link, methods=["GET"])
router.add_api_route("/notes/{note_id}/backlinks", notes_service.note_backlinks, methods=["GET"])
router.add_api_route("/notes/diary-summaries", notes_service.diary_summaries, methods=["GET"])
router.add_api_route("/notes/calendar", notes_service.notes_calendar, methods=["GET"])
router.add_api_route("/notes", notes_service.create_note, methods=["POST"])
router.add_api_route("/notes/{note_id}", notes_service.get_note, methods=["GET"])
router.add_api_route("/notes/{note_id}", notes_service.update_note, methods=["PUT"])
router.add_api_route("/notes/{note_id}", notes_service.delete_note, methods=["DELETE"])
