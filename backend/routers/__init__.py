from fastapi import APIRouter

from routers.admin import router as admin_router
from routers.audit import router as audit_router
from routers.auth import router as auth_router
from routers.health import router as health_router
from routers.knowledge import router as knowledge_router
from routers.ledger import router as ledger_router
from routers.monitor import router as monitor_router
from routers.notes import router as notes_router
from routers.notebook import router as notebook_router
from routers.poem import router as poem_router
from routers.recycle import router as recycle_router
from routers.review import router as review_router
from routers.review_sessions import router as review_sessions_router
from routers.todo import router as todo_router
from routers.trade_plans import router as trade_plans_router
from routers.trading import router as trading_router
from routers.upload import router as upload_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(admin_router)
api_router.include_router(audit_router)
api_router.include_router(upload_router)
api_router.include_router(trading_router)
api_router.include_router(review_router)
api_router.include_router(review_sessions_router)
api_router.include_router(trade_plans_router)
api_router.include_router(knowledge_router)
api_router.include_router(ledger_router)
api_router.include_router(notebook_router)
api_router.include_router(notes_router)
api_router.include_router(todo_router)
api_router.include_router(recycle_router)
api_router.include_router(poem_router)
api_router.include_router(monitor_router)
