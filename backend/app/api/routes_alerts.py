"""Alert history, rule management, acknowledgement and resolution endpoints."""
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.session import get_db
from backend.app.models.models import Alert, AlertRule
from backend.app.schemas.schemas import AlertRuleCreate, AlertRuleSchema, AlertRuleUpdate, AlertSchema
from backend.app.services.traffic_service import TrafficService
from backend.app.core.security import require_roles

router = APIRouter(prefix="/alerts", tags=["Alerts"])


def _alert_query(resolved, severity, camera_id, start_at, end_at, acknowledged):
    query = select(Alert)
    if resolved is not None:
        query = query.where(Alert.is_resolved == resolved)
    if severity:
        query = query.where(Alert.severity == severity)
    if camera_id:
        query = query.where(Alert.camera_id == camera_id)
    if start_at:
        query = query.where(Alert.created_at >= start_at.replace(tzinfo=None))
    if end_at:
        query = query.where(Alert.created_at <= end_at.replace(tzinfo=None))
    if acknowledged is not None:
        query = query.where(Alert.acknowledged_at.is_not(None) if acknowledged else Alert.acknowledged_at.is_(None))
    return query


async def _list_page(db, *, resolved, severity, camera_id, start_at, end_at, acknowledged, limit, offset):
    query = _alert_query(resolved, severity, camera_id, start_at, end_at, acknowledged)
    total = int(await db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0)
    rows = (await db.execute(query.order_by(desc(Alert.created_at), desc(Alert.id)).limit(limit).offset(offset))).scalars().all()
    return {"items": rows, "total": total, "limit": limit, "offset": offset}


@router.get("/rules", response_model=list[AlertRuleSchema])
async def list_alert_rules(limit: int = Query(100, ge=1, le=200), offset: int = Query(0, ge=0), db: AsyncSession = Depends(get_db)):
    return (await db.execute(select(AlertRule).order_by(AlertRule.name).limit(limit).offset(offset))).scalars().all()


@router.post("/rules", response_model=AlertRuleSchema, status_code=201, dependencies=[Depends(require_roles("admin"))])
async def create_alert_rule(payload: AlertRuleCreate, db: AsyncSession = Depends(get_db)):
    rule = AlertRule(**payload.model_dump())
    db.add(rule)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="An alert rule with this name already exists.") from exc
    await db.refresh(rule)
    return rule


@router.patch("/rules/{rule_id}", response_model=AlertRuleSchema, dependencies=[Depends(require_roles("admin"))])
async def update_alert_rule(rule_id: int, payload: AlertRuleUpdate, db: AsyncSession = Depends(get_db)):
    rule = await db.get(AlertRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Alert rule not found.")
    values = {"name": rule.name, "rule_type": rule.rule_type, "severity": rule.severity,
              "configuration": rule.configuration or {}, "enabled": rule.enabled}
    values.update(payload.model_dump(exclude_unset=True))
    try:
        validated = AlertRuleCreate(**values)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    for key, value in validated.model_dump().items():
        setattr(rule, key, value)
    rule.updated_at = datetime.now(timezone.utc)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="An alert rule with this name already exists.") from exc
    await db.refresh(rule)
    return rule


@router.delete("/rules/{rule_id}", status_code=204, dependencies=[Depends(require_roles("admin"))])
async def delete_alert_rule(rule_id: int, db: AsyncSession = Depends(get_db)):
    rule = await db.get(AlertRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Alert rule not found.")
    await db.delete(rule)
    await db.commit()
    return Response(status_code=204)


@router.get("/page")
async def list_alerts_page(
    resolved: bool | None = Query(None), severity: Literal["info", "warning", "medium", "high", "critical"] | None = Query(None),
    camera_id: str | None = Query(None, min_length=1, max_length=20), start_at: datetime | None = Query(None),
    end_at: datetime | None = Query(None), acknowledged: bool | None = Query(None),
    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0, le=100000), db: AsyncSession = Depends(get_db),
):
    if start_at and end_at and start_at > end_at:
        raise HTTPException(status_code=422, detail="start_at must be earlier than or equal to end_at.")
    return await _list_page(db, resolved=resolved, severity=severity, camera_id=camera_id, start_at=start_at,
                            end_at=end_at, acknowledged=acknowledged, limit=limit, offset=offset)


@router.get("", response_model=list[AlertSchema])
async def list_alerts(
    resolved: bool | None = Query(None), severity: Literal["info", "warning", "medium", "high", "critical"] | None = Query(None),
    camera_id: str | None = Query(None, min_length=1, max_length=20), start_at: datetime | None = Query(None),
    end_at: datetime | None = Query(None), acknowledged: bool | None = Query(None),
    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0, le=100000), db: AsyncSession = Depends(get_db),
):
    if start_at and end_at and start_at > end_at:
        raise HTTPException(status_code=422, detail="start_at must be earlier than or equal to end_at.")
    return (await _list_page(db, resolved=resolved, severity=severity, camera_id=camera_id, start_at=start_at,
        end_at=end_at, acknowledged=acknowledged, limit=limit, offset=offset))["items"]


@router.patch("/{alert_id}/acknowledge", response_model=AlertSchema, dependencies=[Depends(require_roles("admin", "operator"))])
async def acknowledge_alert(alert_id: int, db: AsyncSession = Depends(get_db)):
    alert = await db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail=f"Alert with ID {alert_id} not found.")
    if alert.acknowledged_at is None:
        alert.acknowledged_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(alert)
    return alert


@router.patch("/{alert_id}/resolve", response_model=AlertSchema, dependencies=[Depends(require_roles("admin", "operator"))])
async def resolve_alert(alert_id: int, db: AsyncSession = Depends(get_db)):
    alert = await TrafficService.resolve_alert(db, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert with ID {alert_id} not found.")
    return alert
