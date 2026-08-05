from fastapi import APIRouter

from app.api.v1.admin import router as admin_router
from app.api.v1.auth import router as auth_router
from app.api.v1.customer import router as customer_router
from app.api.v1.employee import router as employee_router
from app.api.v1.events import router as events_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(customer_router)
api_router.include_router(employee_router)
api_router.include_router(admin_router)
api_router.include_router(events_router)
