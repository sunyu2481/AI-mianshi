from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ...core.database import get_db
from ...models.analysis import AnalysisResult
from ...models.answer import Answer
from ...models.paper import Paper, PaperItem
from ...models.paper_session import PaperSession
from ...models.question import Question
from ...schemas.paper import (
    PaperCreate,
    PaperListResponse,
    PaperResponse,
    PaperUpdate,
)

router = APIRouter(prefix="/papers", tags=["套卷管理"])


@router.get("", response_model=PaperListResponse)
async def list_papers(
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=100),
    keyword: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """分页获取套卷列表，支持多词筛选。"""
    query = select(Paper).options(selectinload(Paper.items))
    count_query = select(func.count(Paper.id))

    keywords = [item.strip().lower() for item in (keyword or "").split() if item.strip()]
    for item in keywords:
        pattern = f"%{item}%"
        filter_condition = or_(
            func.lower(Paper.title).like(pattern),
            func.lower(func.coalesce(Paper.description, "")).like(pattern),
        )
        query = query.where(filter_condition)
        count_query = count_query.where(filter_condition)

    query = query.order_by(Paper.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    papers = result.scalars().all()

    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    return PaperListResponse(
        items=[PaperResponse.model_validate(p) for p in papers],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=PaperResponse)
async def create_paper(
    data: PaperCreate,
    db: AsyncSession = Depends(get_db),
):
    """新建套卷。"""
    if data.question_ids:
        result = await db.execute(
            select(Question.id).where(Question.id.in_(data.question_ids))
        )
        existing_ids = {row[0] for row in result.all()}
        missing_ids = set(data.question_ids) - existing_ids
        if missing_ids:
            raise HTTPException(
                status_code=400,
                detail=f"以下题目不存在: {sorted(missing_ids)}",
            )

    paper = Paper(
        title=data.title,
        description=data.description,
        time_limit_seconds=data.time_limit_seconds,
    )
    db.add(paper)
    await db.flush()

    if data.question_ids:
        for idx, question_id in enumerate(data.question_ids, start=1):
            item = PaperItem(
                paper_id=paper.id,
                question_id=question_id,
                sort_order=idx,
            )
            db.add(item)

    await db.commit()
    await db.refresh(paper)

    result = await db.execute(
        select(Paper)
        .options(selectinload(Paper.items))
        .where(Paper.id == paper.id)
    )
    paper = result.scalar_one()

    return PaperResponse.model_validate(paper)


@router.get("/{paper_id}", response_model=PaperResponse)
async def get_paper(
    paper_id: int,
    db: AsyncSession = Depends(get_db),
):
    """获取套卷详情。"""
    result = await db.execute(
        select(Paper)
        .options(selectinload(Paper.items))
        .where(Paper.id == paper_id)
    )
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail="套卷不存在")
    return PaperResponse.model_validate(paper)


@router.put("/{paper_id}", response_model=PaperResponse)
async def update_paper(
    paper_id: int,
    data: PaperUpdate,
    db: AsyncSession = Depends(get_db),
):
    """更新套卷。"""
    result = await db.execute(select(Paper).where(Paper.id == paper_id))
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail="套卷不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(paper, key, value)

    await db.commit()
    await db.refresh(paper)
    return PaperResponse.model_validate(paper)


@router.delete("/{paper_id}")
async def delete_paper(
    paper_id: int,
    db: AsyncSession = Depends(get_db),
):
    """删除套卷，并物理删除其独占题目及关联练习记录。"""
    result = await db.execute(
        select(Paper)
        .options(selectinload(Paper.items))
        .where(Paper.id == paper_id)
    )
    paper = result.scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail="套卷不存在")

    question_ids = [item.question_id for item in paper.items]
    exclusive_question_ids: list[int] = []
    questions_to_delete: list[Question] = []
    answers_to_delete: list[Answer] = []
    paper_sessions_to_delete: list[PaperSession] = []
    analyses_to_delete: list[AnalysisResult] = []

    if question_ids:
        reusable_question_result = await db.execute(
            select(PaperItem.question_id)
            .where(
                PaperItem.question_id.in_(question_ids),
                PaperItem.paper_id != paper_id,
            )
        )
        reusable_question_ids = {row[0] for row in reusable_question_result.all()}

        exclusive_question_ids = [
            question_id
            for question_id in question_ids
            if question_id not in reusable_question_ids
        ]

        if exclusive_question_ids:
            question_result = await db.execute(
                select(Question).where(Question.id.in_(exclusive_question_ids))
            )
            questions_to_delete = question_result.scalars().all()

    answer_conditions = [Answer.paper_id == paper_id]
    if exclusive_question_ids:
        answer_conditions.append(Answer.question_id.in_(exclusive_question_ids))

    answer_result = await db.execute(
        select(Answer).where(or_(*answer_conditions))
    )
    answers_to_delete = answer_result.scalars().all()
    answer_ids = [answer.id for answer in answers_to_delete]
    paper_session_ids = {
        answer.paper_session_id
        for answer in answers_to_delete
        if answer.paper_session_id
    }

    if answer_ids:
        analysis_result = await db.execute(
            select(AnalysisResult).where(AnalysisResult.answer_id.in_(answer_ids))
        )
        analyses_to_delete = analysis_result.scalars().all()

    session_conditions = [PaperSession.paper_id == paper_id]
    if paper_session_ids:
        session_conditions.append(PaperSession.paper_session_id.in_(paper_session_ids))

    paper_session_result = await db.execute(
        select(PaperSession).where(or_(*session_conditions))
    )
    paper_sessions_to_delete = paper_session_result.scalars().all()

    for analysis in analyses_to_delete:
        await db.delete(analysis)

    for answer in answers_to_delete:
        await db.delete(answer)

    for paper_session in paper_sessions_to_delete:
        await db.delete(paper_session)

    await db.delete(paper)
    await db.flush()

    for question in questions_to_delete:
        await db.delete(question)

    await db.commit()
    return {"message": "删除成功"}


@router.post("/{paper_id}/items")
async def add_paper_item(
    paper_id: int,
    question_id: int,
    db: AsyncSession = Depends(get_db),
):
    """向套卷追加题目。"""
    result = await db.execute(select(Paper).where(Paper.id == paper_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="套卷不存在")

    result = await db.execute(select(Question).where(Question.id == question_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="题目不存在")

    max_order_result = await db.execute(
        select(func.max(PaperItem.sort_order)).where(PaperItem.paper_id == paper_id)
    )
    max_order = max_order_result.scalar() or 0

    item = PaperItem(
        paper_id=paper_id,
        question_id=question_id,
        sort_order=max_order + 1,
    )
    db.add(item)
    await db.commit()
    return {"message": "添加成功"}


@router.delete("/{paper_id}/items/{item_id}")
async def remove_paper_item(
    paper_id: int,
    item_id: int,
    db: AsyncSession = Depends(get_db),
):
    """从套卷移除题目。"""
    result = await db.execute(
        select(PaperItem).where(
            PaperItem.id == item_id,
            PaperItem.paper_id == paper_id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="题目项不存在")

    await db.delete(item)
    await db.commit()
    return {"message": "移除成功"}
