from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from ...core.database import get_db
from ...models.answer import Answer
from ...models.analysis import AnalysisResult
from ...models.paper_session import PaperSession
from ...schemas.answer import AnswerWithAnalysis

router = APIRouter(prefix="/history", tags=["历史记录"])


@router.get("/single")
async def get_single_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """获取单题练习历史（按日期分组）"""
    # 查询单题模式的作答
    query = select(Answer).where(Answer.mode == "single")
    query = query.options(
        selectinload(Answer.analysis),
        selectinload(Answer.question)
    )
    query = query.order_by(Answer.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    answers = result.scalars().all()

    # 按日期分组
    grouped = {}
    for a in answers:
        date = a.practice_date
        if date not in grouped:
            grouped[date] = []
        item = AnswerWithAnalysis.model_validate(a)
        item.question_content = a.question.content if a.question else None
        grouped[date].append(item)

    # 总数
    count_result = await db.execute(
        select(func.count(Answer.id)).where(Answer.mode == "single")
    )
    total = count_result.scalar()

    return {
        "items": grouped,
        "total": total,
        "page": page,
        "page_size": page_size
    }


@router.get("/paper")
async def get_paper_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """获取套卷练习历史（按日期分组）"""
    session_result = await db.execute(
        select(
            Answer.paper_session_id,
            func.max(Answer.created_at).label("latest_created_at")
        )
        .where(
            Answer.mode == "paper",
            Answer.paper_session_id.isnot(None)
        )
        .group_by(Answer.paper_session_id)
        .order_by(func.max(Answer.created_at).desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    session_rows = session_result.all()
    session_ids = [row.paper_session_id for row in session_rows if row.paper_session_id]

    grouped = {}
    if session_ids:
        answer_result = await db.execute(
            select(Answer)
            .options(selectinload(Answer.question), selectinload(Answer.paper))
            .where(Answer.paper_session_id.in_(session_ids))
            .order_by(Answer.created_at)
        )
        answers = answer_result.scalars().all()

        summary_result = await db.execute(
            select(PaperSession).where(PaperSession.paper_session_id.in_(session_ids))
        )
        summary_map = {
            session.paper_session_id: session
            for session in summary_result.scalars().all()
        }

        answers_by_session: dict[str, list[Answer]] = {}
        for answer in answers:
            session_id = answer.paper_session_id or ""
            answers_by_session.setdefault(session_id, []).append(answer)

        for session_id in session_ids:
            session_answers = answers_by_session.get(session_id, [])
            if not session_answers:
                continue

            summary = summary_map.get(session_id)
            first_answer = session_answers[0]
            practice_date = summary.practice_date if summary else first_answer.practice_date
            paper_title = (
                summary.paper_title
                if summary
                else (first_answer.paper.title if first_answer.paper else "套卷练习")
            )
            total_duration = (
                summary.total_duration_seconds
                if summary and summary.total_duration_seconds is not None
                else sum(answer.duration_seconds or 0 for answer in session_answers)
            )
            time_limit_seconds = (
                summary.time_limit_seconds
                if summary and summary.time_limit_seconds is not None
                else (first_answer.paper.time_limit_seconds if first_answer.paper else None)
            )

            if practice_date not in grouped:
                grouped[practice_date] = []

            grouped[practice_date].append({
                "paper_session_id": session_id,
                "paper_id": summary.paper_id if summary else first_answer.paper_id,
                "paper_title": paper_title,
                "question_count": summary.question_count if summary else len(session_answers),
                "time_limit_seconds": time_limit_seconds,
                "total_duration_seconds": total_duration,
                "started_at": (summary.started_at if summary else first_answer.started_at).isoformat(),
                "finished_at": (
                    (summary.finished_at if summary and summary.finished_at else session_answers[-1].finished_at)
                    .isoformat()
                    if (summary and summary.finished_at) or session_answers[-1].finished_at
                    else None
                ),
                "practice_date": practice_date,
                "analysis_score": summary.analysis_score if summary else None,
                "analysis_feedback": summary.analysis_feedback if summary else None,
                "model_name": summary.model_name if summary else None,
                "answer_ids": [answer.id for answer in session_answers],
                "answers": [
                    {
                        "id": answer.id,
                        "question_id": answer.question_id,
                        "question_content": answer.question.content if answer.question else None,
                        "transcript": answer.transcript,
                        "duration_seconds": answer.duration_seconds,
                    }
                    for answer in session_answers
                ]
            })

    count_result = await db.execute(
        select(func.count(func.distinct(Answer.paper_session_id))).where(
            Answer.mode == "paper",
            Answer.paper_session_id.isnot(None)
        )
    )
    total = count_result.scalar() or 0

    return {
        "items": grouped,
        "total": total,
        "page": page,
        "page_size": page_size
    }


@router.get("/trends")
async def get_score_trends(
    mode: str = Query("single"),
    days: int = Query(30, ge=7, le=90),
    db: AsyncSession = Depends(get_db)
):
    """获取分数趋势数据"""
    from datetime import datetime, timedelta

    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    daily_scores = {}

    if mode == "paper":
        result = await db.execute(
            select(PaperSession)
            .where(
                PaperSession.practice_date >= start_date,
                PaperSession.analysis_score.isnot(None)
            )
            .order_by(PaperSession.practice_date)
        )
        sessions = result.scalars().all()

        for session in sessions:
            date = session.practice_date
            if date not in daily_scores:
                daily_scores[date] = {"scores": [], "count": 0}
            daily_scores[date]["scores"].append(session.analysis_score)
            daily_scores[date]["count"] += 1
    else:
        query = select(Answer, AnalysisResult).join(
            AnalysisResult, Answer.id == AnalysisResult.answer_id
        ).where(
            Answer.mode == mode,
            Answer.practice_date >= start_date,
            AnalysisResult.score.isnot(None)
        ).order_by(Answer.practice_date)

        result = await db.execute(query)
        rows = result.all()

        for answer, analysis in rows:
            date = answer.practice_date
            if date not in daily_scores:
                daily_scores[date] = {"scores": [], "count": 0}
            daily_scores[date]["scores"].append(analysis.score)
            daily_scores[date]["count"] += 1

    # 计算每日平均分
    trends = []
    for date, data in sorted(daily_scores.items()):
        avg_score = sum(data["scores"]) / len(data["scores"])
        trends.append({
            "date": date,
            "avg_score": round(avg_score, 1),
            "count": data["count"]
        })

    return {"trends": trends, "mode": mode}
