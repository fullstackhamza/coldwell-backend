from fastapi import APIRouter, Depends, UploadFile

from ..auth_utils import get_current_admin_id
from ..models.common import CamelModel
from ..storage import save_upload

router = APIRouter(prefix="/api/uploads", tags=["uploads"])


class UploadResult(CamelModel):
    url: str


@router.post("", response_model=UploadResult, status_code=201)
def upload_image(
    file: UploadFile,
    # Admin-only — same as product create/update/delete. Prevents random
    # visitors from filling your disk with arbitrary files.
    _admin_id: str = Depends(get_current_admin_id),
):
    url = save_upload(file)
    return UploadResult(url=url)
