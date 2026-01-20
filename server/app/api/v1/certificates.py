"""Certificate management endpoints."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.certificate import CertificateStatus
from app.models.user import User
from app.schemas.certificate import (
    CertificateIssueRequest,
    CertificateListResponse,
    CertificateResponse,
    CertificateRevokeRequest,
    CertificateVerifyResponse,
)
from app.services.agent_service import AgentService
from app.services.certificate_service import CertificateService
from app.services.evaluation_service import EvaluationService

router = APIRouter()


@router.post("", response_model=CertificateResponse, status_code=status.HTTP_201_CREATED)
async def issue_certificate(
    data: CertificateIssueRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CertificateResponse:
    """Issue a trust certificate based on evaluation results."""
    # Verify agent access
    agent_service = AgentService(db)
    agent = await agent_service.get(data.agent_id)

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    if agent.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to issue certificate for this agent",
        )

    # Verify evaluation exists and is completed
    eval_service = EvaluationService(db)
    evaluation = await eval_service.get(data.evaluation_id)

    if not evaluation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation not found",
        )

    if evaluation.agent_id != data.agent_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Evaluation does not belong to this agent",
        )

    from app.models.evaluation import EvaluationStatus
    if evaluation.status != EvaluationStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Evaluation is not completed",
        )

    # Issue certificate
    cert_service = CertificateService(db)

    try:
        certificate = await cert_service.issue(
            agent_id=data.agent_id,
            evaluation_id=data.evaluation_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return await cert_service.to_response(certificate)


@router.get("", response_model=CertificateListResponse)
async def list_certificates(
    agent_id: Optional[UUID] = None,
    status_filter: Optional[CertificateStatus] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CertificateListResponse:
    """List certificates."""
    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must belong to an organization",
        )

    # If agent_id provided, verify access
    if agent_id:
        agent_service = AgentService(db)
        agent = await agent_service.get(agent_id)
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found",
            )
        if agent.organization_id != current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this agent's certificates",
            )

    cert_service = CertificateService(db)
    certificates, total = await cert_service.list(
        organization_id=current_user.organization_id,
        agent_id=agent_id,
        status=status_filter,
        page=page,
        page_size=page_size,
    )

    items = [await cert_service.to_response(c) for c in certificates]

    return CertificateListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.get("/{certificate_id}", response_model=CertificateResponse)
async def get_certificate(
    certificate_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CertificateResponse:
    """Get certificate details."""
    cert_service = CertificateService(db)
    certificate = await cert_service.get(certificate_id)

    if not certificate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificate not found",
        )

    # Verify access through agent
    agent_service = AgentService(db)
    agent = await agent_service.get(certificate.agent_id)

    if not agent or agent.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this certificate",
        )

    return await cert_service.to_response(certificate)


@router.get("/{certificate_id}/verify", response_model=CertificateVerifyResponse)
async def verify_certificate(
    certificate_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> CertificateVerifyResponse:
    """
    Verify a certificate's validity.

    This endpoint is public - no authentication required.
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


@router.post("/{certificate_id}/revoke", response_model=CertificateResponse)
async def revoke_certificate(
    certificate_id: UUID,
    data: CertificateRevokeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CertificateResponse:
    """Revoke a certificate."""
    cert_service = CertificateService(db)
    certificate = await cert_service.get(certificate_id)

    if not certificate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificate not found",
        )

    # Verify access through agent
    agent_service = AgentService(db)
    agent = await agent_service.get(certificate.agent_id)

    if not agent or agent.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to revoke this certificate",
        )

    if certificate.status == CertificateStatus.revoked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Certificate is already revoked",
        )

    certificate = await cert_service.revoke(certificate_id, data.reason)
    return await cert_service.to_response(certificate)


@router.get("/{certificate_id}/chain")
async def get_certificate_chain(
    certificate_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get the full certificate chain for verification.

    This endpoint is public - no authentication required.
    Returns the certificate and its signing chain up to root CA.
    """
    cert_service = CertificateService(db)
    certificate = await cert_service.get(certificate_id)

    if not certificate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificate not found",
        )

    chain = await cert_service.get_certificate_chain(certificate_id)
    return chain
