"""Dashboard-Web-Router."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.templating import templates
from app.routers.web.helpers import flash_context
from app.services import auswertung as auswertung_service

router = APIRouter(tags=["Web-Dashboard"])


@router.get("/", response_class=HTMLResponse)
async def view_dashboard(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
):
    summary = await auswertung_service.get_dashboard_summary(session)
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "active_nav": "dashboard",
            "summary": summary,
            **flash_context(request),
        },
    )
