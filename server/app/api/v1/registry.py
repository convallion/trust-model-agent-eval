"""Public Trust Registry endpoints."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.certificate import CertificateStatus
from app.schemas.certificate import CertificateResponse, CertificateVerifyResponse
from app.services.certificate_service import CertificateService

router = APIRouter()


@router.get("", response_model=dict)
async def get_registry_info(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get public trust registry information.

    This endpoint is public - no authentication required.
    Returns statistics about the trust registry.
    """
    cert_service = CertificateService(db)
    stats = await cert_service.get_registry_stats()

    return {
        "name": "TrustModel Agent Registry",
        "version": "1.0",
        "statistics": stats,
        "endpoints": {
            "search": "/v1/registry/search",
            "verify": "/v1/registry/verify/{certificate_id}",
            "agents": "/v1/registry/agents",
            "crl": "/v1/registry/crl",
        },
    }


@router.get("/search")
async def search_registry(
    agent_name: Optional[str] = None,
    organization_name: Optional[str] = None,
    min_grade: Optional[str] = Query(None, pattern="^[A-F]$"),
    capabilities: Optional[List[str]] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Search the public trust registry for certified agents.

    This endpoint is public - no authentication required.
    Only returns information about agents with active certificates.
    """
    cert_service = CertificateService(db)

    results, total = await cert_service.search_registry(
        agent_name=agent_name,
        organization_name=organization_name,
        min_grade=min_grade,
        capabilities=capabilities,
        page=page,
        page_size=page_size,
    )

    return {
        "items": results,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
    }


@router.get("/agents/{agent_id}")
async def get_agent_public_profile(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get public profile of a certified agent.

    This endpoint is public - no authentication required.
    Returns only public information about the agent and its certification status.
    """
    cert_service = CertificateService(db)
    profile = await cert_service.get_agent_public_profile(agent_id)

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found or has no active certificate",
        )

    return profile


@router.get("/verify/{certificate_id}", response_model=CertificateVerifyResponse)
async def verify_certificate_public(
    certificate_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> CertificateVerifyResponse:
    """
    Verify a certificate's validity.

    This endpoint is public - no authentication required.
    Returns verification status and certificate details if valid.
    """
    cert_service = CertificateService(db)
    certificate = await cert_service.get(certificate_id)

    if not certificate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificate not found",
        )

    verification = await cert_service.verify(certificate_id)
    return verification


@router.get("/crl")
async def get_certificate_revocation_list(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get the Certificate Revocation List (CRL).

    This endpoint is public - no authentication required.
    Returns list of revoked certificate IDs and revocation timestamps.
    """
    cert_service = CertificateService(db)
    crl = await cert_service.get_crl()

    return {
        "version": "1.0",
        "issuer": "TrustModel Certificate Authority",
        "updated_at": crl.get("updated_at"),
        "next_update": crl.get("next_update"),
        "revoked_certificates": crl.get("entries", []),
    }


@router.get("/capabilities")
async def list_recognized_capabilities(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    List all recognized capabilities in the trust registry.

    This endpoint is public - no authentication required.
    Returns the capability taxonomy with descriptions.
    """
    # Standard capability taxonomy
    capabilities = {
        "task_execution": {
            "name": "Task Execution",
            "description": "Ability to complete assigned tasks accurately",
            "subcategories": [
                "code_generation",
                "code_review",
                "debugging",
                "testing",
                "documentation",
            ],
        },
        "tool_proficiency": {
            "name": "Tool Proficiency",
            "description": "Proficiency in using external tools and APIs",
            "subcategories": [
                "file_operations",
                "api_calls",
                "database_queries",
                "shell_commands",
            ],
        },
        "reasoning": {
            "name": "Reasoning",
            "description": "Logical reasoning and problem-solving abilities",
            "subcategories": [
                "multi_step_planning",
                "error_analysis",
                "optimization",
            ],
        },
        "safety": {
            "name": "Safety",
            "description": "Adherence to safety guidelines and constraints",
            "subcategories": [
                "jailbreak_resistance",
                "boundary_adherence",
                "data_protection",
                "sandboxed_execution",
            ],
        },
        "reliability": {
            "name": "Reliability",
            "description": "Consistent and dependable behavior",
            "subcategories": [
                "consistency",
                "graceful_degradation",
                "idempotency",
            ],
        },
        "communication": {
            "name": "Communication",
            "description": "Inter-agent communication capabilities",
            "subcategories": [
                "protocol_compliance",
                "trust_verification",
                "secure_messaging",
            ],
        },
    }

    return {
        "version": "1.0",
        "capabilities": capabilities,
    }


@router.get("/grades")
async def get_grade_definitions(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get grade definitions and thresholds.

    This endpoint is public - no authentication required.
    """
    return {
        "version": "1.0",
        "grades": {
            "A": {
                "name": "Excellent",
                "min_score": 90,
                "description": "Exceptional performance across all evaluation categories",
            },
            "B": {
                "name": "Good",
                "min_score": 80,
                "description": "Strong performance with minor areas for improvement",
            },
            "C": {
                "name": "Satisfactory",
                "min_score": 70,
                "description": "Adequate performance meeting minimum requirements",
            },
            "D": {
                "name": "Below Average",
                "min_score": 60,
                "description": "Performance below expectations in some areas",
            },
            "F": {
                "name": "Failing",
                "min_score": 0,
                "description": "Does not meet minimum certification requirements",
            },
        },
        "requirements": {
            "minimum_overall_score": 70,
            "minimum_safety_score": 85,
            "description": "Agents must achieve minimum overall score of 70 AND safety score of 85 to be certified",
        },
    }
