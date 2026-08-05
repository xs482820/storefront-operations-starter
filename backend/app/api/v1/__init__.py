from fastapi import APIRouter

from app.api.v1.admin import router as admin_router
from app.api.v1.admin_ai import router as admin_ai_router
from app.api.v1.admin_me import router as admin_me_router
from app.api.v1.admin_users_extra import router as admin_users_extra_router
from app.api.v1.auth import router as auth_router
from app.api.v1.customer import router as customer_router
from app.api.v1.employee import router as employee_router
from app.api.v1.events import router as events_router
from app.api.v1.payments import router as payments_router
from app.api.v1.print_gateway import router as print_gateway_router
from app.api.v1.storefront_extra import router as storefront_extra_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(customer_router)
api_router.include_router(employee_router)
api_router.include_router(payments_router)
api_router.include_router(print_gateway_router)
api_router.include_router(admin_router)
api_router.include_router(admin_ai_router)
api_router.include_router(admin_users_extra_router)
api_router.include_router(admin_me_router)
api_router.include_router(events_router)
api_router.include_router(storefront_extra_router)
