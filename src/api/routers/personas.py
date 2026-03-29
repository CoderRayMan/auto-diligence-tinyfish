"""
/api/personas — List available role-based scan presets.
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, HTTPException

from ..schemas import Persona, list_personas, get_persona

router = APIRouter(prefix="/personas", tags=["personas"])


@router.get("", response_model=List[Persona])
async def get_personas() -> List[Persona]:
    """Return all available personas with demo targets."""
    return list_personas()


@router.get("/{persona_id}", response_model=Persona)
async def get_persona_by_id(persona_id: str) -> Persona:
    """Return a single persona by ID."""
    p = get_persona(persona_id)
    if p is None:
        raise HTTPException(status_code=404, detail=f"Persona '{persona_id}' not found")
    return p
