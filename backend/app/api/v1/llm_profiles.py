from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.domain import LLMProfile
from app.repositories.core import update_llm_profile_presentation
from app.schemas.llm_profiles import LLMProfileCreate, LLMProfilePatch, LLMProfileRead

router = APIRouter(prefix="/admin/llm-profiles", tags=["admin-llm-profiles"])


@router.get("", response_model=list[LLMProfileRead])
def list_profiles(db: Session = Depends(get_db)) -> list[LLMProfile]:
    return list(db.scalars(select(LLMProfile).order_by(LLMProfile.provider, LLMProfile.model)))


@router.post("", response_model=LLMProfileRead, status_code=status.HTTP_201_CREATED)
def create_profile(payload: LLMProfileCreate, db: Session = Depends(get_db)) -> LLMProfile:
    # Qualification is governed: every new profile starts UNTESTED and cannot be
    # self-asserted by the caller (docs/qualification/MODEL_QUALIFICATION.md).
    profile = LLMProfile(**payload.model_dump(), qualification_status="UNTESTED", qualification_summary={})
    if profile.is_default:
        for other in db.scalars(select(LLMProfile)):
            other.is_default = False
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@router.get("/{profile_id}", response_model=LLMProfileRead)
def get_profile(profile_id: UUID, db: Session = Depends(get_db)) -> LLMProfile:
    profile = db.get(LLMProfile, profile_id)
    if not profile:
        raise HTTPException(404, "LLM profile not found")
    return profile


@router.patch("/{profile_id}", response_model=LLMProfileRead)
def patch_profile(profile_id: UUID, payload: LLMProfilePatch, db: Session = Depends(get_db)) -> LLMProfile:
    profile = db.get(LLMProfile, profile_id)
    if not profile:
        raise HTTPException(404, "LLM profile not found")
    update_llm_profile_presentation(db, profile, **payload.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(profile)
    return profile
