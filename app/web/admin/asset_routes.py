"""資産管理"""
import uuid
from datetime import datetime, date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db.models import Asset, AssetInventory, User
from app.db.session import get_db
from app.web.deps import templates

router = APIRouter(prefix="/admin")

ASSET_TYPES = ["PC", "モニター", "スマートフォン", "サーバー", "ネットワーク機器", "その他"]


@router.get("/assets", response_class=HTMLResponse)
def asset_list(request: Request, db: Session = Depends(get_db)):
    assets = db.query(Asset).order_by(Asset.asset_type, Asset.name).all()
    users = db.query(User).filter(User.is_active == 1).all()
    users_map = {u.id: u for u in users}

    # 直近6ヶ月の棚卸期間を生成
    today = date.today()
    periods = []
    for i in range(5, -1, -1):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        periods.append(f"{y}-{m:02d}")

    # 棚卸マップ: {asset_id: {period: AssetInventory}}
    all_inv = db.query(AssetInventory).all()
    inv_map = {}
    for inv in all_inv:
        inv_map.setdefault(inv.asset_id, {})[inv.inventory_date] = inv

    return templates.TemplateResponse(request, "admin/assets.html", context={
        "assets": assets,
        "users": users,
        "users_map": users_map,
        "periods": periods,
        "inv_map": inv_map,
        "asset_types": ASSET_TYPES,
    })


@router.post("/assets/new")
def asset_new(
    name: str = Form(...),
    asset_type: str = Form("PC"),
    management_code: str = Form(""),
    description: str = Form(""),
    assigned_user_id: str = Form(""),
    db: Session = Depends(get_db),
):
    now = datetime.utcnow().isoformat()
    db.add(Asset(
        id=str(uuid.uuid4()),
        name=name,
        asset_type=asset_type,
        management_code=management_code,
        description=description,
        assigned_user_id=assigned_user_id,
        is_active=1,
        created_at=now,
    ))
    db.commit()
    return RedirectResponse("/admin/assets", status_code=303)


@router.post("/assets/{asset_id}/delete")
def asset_delete(asset_id: str, db: Session = Depends(get_db)):
    a = db.query(Asset).filter(Asset.id == asset_id).first()
    if a:
        db.delete(a)
        db.commit()
    return RedirectResponse("/admin/assets", status_code=303)


@router.post("/assets/inventory/update")
def inventory_update(
    request: Request,
    asset_id: str = Form(...),
    period: str = Form(...),
    status: str = Form("unchecked"),
    note: str = Form(""),
    db: Session = Depends(get_db),
):
    changed_by = getattr(getattr(request.state, "current_user", None), "name", "管理者")
    inv = db.query(AssetInventory).filter(
        AssetInventory.asset_id == asset_id,
        AssetInventory.inventory_date == period,
    ).first()
    now = datetime.utcnow().isoformat()
    if inv:
        inv.status = status
        inv.note = note
        inv.checked_by = changed_by
    else:
        db.add(AssetInventory(
            id=str(uuid.uuid4()),
            asset_id=asset_id,
            inventory_date=period,
            status=status,
            note=note,
            checked_by=changed_by,
            created_at=now,
        ))
    db.commit()
    return RedirectResponse("/admin/assets", status_code=303)
