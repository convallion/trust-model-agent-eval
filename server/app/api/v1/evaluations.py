"""Evaluation management endpoints."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.evaluation import EvaluationStatus
from app.models.user import User
from app.schemas.evaluation import (
    EvaluationListResponse,
    EvaluationRequest,
    EvaluationResponse,
    EvaluationSuiteResult,
)
from app.services.agent_service import AgentService
from app.services.evaluation_service import EvaluationService

router = APIRouter()


async def run_evaluation_background(
    evaluation_id: UUID,
    db_url: str,
) -> None:
    """Background task to run evaluation."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker

    engine = create_async_engine(db_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        service = EvaluationService(session)
        await service.run_evaluation(evaluation_id)
        await session.commit()

    await engine.dispose()


@router.post("", response_model=EvaluationResponse, status_code=status.HTTP_201_CREATED)
async def start_evaluation(
    data: EvaluationRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EvaluationResponse:
    """Start an evaluation run for an agent."""
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
            detail="Not authorized to evaluate this agent",
        )

    # Create evaluation run
    eval_service = EvaluationService(db)
    evaluation = await eval_service.create(data)

    # Queue background evaluation
    from app.config import settings
    background_tasks.add_task(
        run_evaluation_background,
        evaluation.id,
        settings.database_url,
    )

    return await eval_service.to_response(evaluation)


@router.get("", response_model=EvaluationListResponse)
async def list_evaluations(
    agent_id: Optional[UUID] = None,
    status_filter: Optional[EvaluationStatus] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EvaluationListResponse:
    """List evaluation runs."""
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
                detail="Not authorized to access this agent's evaluations",
            )

    eval_service = EvaluationService(db)
    evaluations, total = await eval_service.list(
        organization_id=current_user.organization_id,
        agent_id=agent_id,
        status=status_filter,
        page=page,
        page_size=page_size,
    )

    items = [await eval_service.to_response(e) for e in evaluations]

    return EvaluationListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.get("/{evaluation_id}", response_model=EvaluationResponse)
async def get_evaluation(
    evaluation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EvaluationResponse:
    """Get evaluation details and results."""
    eval_service = EvaluationService(db)
    evaluation = await eval_service.get(evaluation_id)

    if not evaluation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation not found",
        )

    # Verify access through agent
    agent_service = AgentService(db)
    agent = await agent_service.get(evaluation.agent_id)

    if not agent or agent.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this evaluation",
        )

    return await eval_service.to_response(evaluation, include_details=True)


@router.get("/{evaluation_id}/suites/{suite_name}", response_model=EvaluationSuiteResult)
async def get_suite_results(
    evaluation_id: UUID,
    suite_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EvaluationSuiteResult:
    """Get detailed results for a specific evaluation suite."""
    eval_service = EvaluationService(db)
    evaluation = await eval_service.get(evaluation_id)

    if not evaluation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation not found",
        )

    # Verify access through agent
    agent_service = AgentService(db)
    agent = await agent_service.get(evaluation.agent_id)

    if not agent or agent.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this evaluation",
        )

    # Get suite results
    suite_results = await eval_service.get_suite_results(evaluation_id, suite_name)

    if not suite_results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Suite '{suite_name}' not found in evaluation",
        )

    return suite_results


@router.post("/{evaluation_id}/cancel", response_model=EvaluationResponse)
async def cancel_evaluation(
    evaluation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EvaluationResponse:
    """Cancel a running evaluation."""
    eval_service = EvaluationService(db)
    evaluation = await eval_service.get(evaluation_id)

    if not evaluation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation not found",
        )

    # Verify access through agent
    agent_service = AgentService(db)
    agent = await agent_service.get(evaluation.agent_id)

    if not agent or agent.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to cancel this evaluation",
        )

    if evaluation.status not in [EvaluationStatus.pending, EvaluationStatus.running]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel evaluation with status '{evaluation.status.value}'",
        )

    evaluation = await eval_service.cancel(evaluation_id)
    return await eval_service.to_response(evaluation)
