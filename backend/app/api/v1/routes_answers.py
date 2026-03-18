from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import datetime
import asyncio
import logging
import json
from ...core.database import get_db, async_session_maker
from ...models.answer import Answer
from ...models.analysis import AnalysisResult
from ...models.paper import Paper
from ...models.paper_session import PaperSession
from ...models.question import Question
from ...schemas.answer import (
    AnswerCreate,
    AnswerResponse,
    AnswerWithAnalysis,
    AnalysisResultResponse,
    HistoryAnalyzeRequest,
    PaperAnalyzeRequest,
    PaperSessionCreate,
    PaperSessionResponse,
)
from ...services.analyze_service import AnalyzeService
import re

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/answers", tags=["作答管理"])

# 分析锁（简单实现）
analysis_locks: dict[int, bool] = {}
paper_analysis_locks: dict[str, bool] = {}


def extract_score_from_feedback(feedback: str | None) -> float | None:
    """从分析文本中提取总分。"""
    if not feedback:
        return None

    patterns = (
        r"(?:整体评分|总体评分)\s*[：:]\s*(\d+(?:\.\d+)?)",
        r"(?:整体得分|总体得分)\s*[：:]\s*(\d+(?:\.\d+)?)",
    )

    for pattern in patterns:
        score_match = re.search(pattern, feedback)
        if score_match:
            return float(score_match.group(1))

    return None


def build_paper_analysis_payload(
    answers: list[Answer],
    time_limit_seconds: int | None
) -> tuple[str, str, int, int]:
    """构建套卷分析所需的题目内容、作答时长和总用时。"""
    paper_content_lines = []
    time_details_lines = []
    total_duration = 0

    for idx, answer in enumerate(answers, 1):
        question_text = answer.question.content if answer.question else "未知题目"
        answer_text = answer.transcript or "未作答"
        duration = answer.duration_seconds or 0
        total_duration += duration

        paper_content_lines.append(
            f"### 第 {idx} 题\n"
            f"**题目**: {question_text}\n"
            f"**作答**: {answer_text}\n"
        )
        time_details_lines.append(f"第 {idx} 题: {duration} 秒")

    paper_content = "\n".join(paper_content_lines)
    time_details = "\n".join(time_details_lines)
    analysis_time_limit = time_limit_seconds or total_duration

    return paper_content, time_details, total_duration, analysis_time_limit


async def ensure_paper_session_record(
    db: AsyncSession,
    session_id: str,
    answers: list[Answer],
    fallback_time_limit: int | None = None
) -> PaperSession:
    """确保套卷会话记录存在，兼容旧数据。"""
    result = await db.execute(
        select(PaperSession).where(PaperSession.paper_session_id == session_id)
    )
    paper_session = result.scalar_one_or_none()
    if paper_session:
        return paper_session

    first_answer = answers[0]
    paper_title = (
        first_answer.paper.title
        if getattr(first_answer, "paper", None)
        else "套卷练习"
    )
    total_duration = sum(answer.duration_seconds or 0 for answer in answers)
    finished_candidates = [answer.finished_at or answer.started_at for answer in answers]

    paper_session = PaperSession(
        paper_session_id=session_id,
        paper_id=first_answer.paper_id,
        paper_title=paper_title,
        time_limit_seconds=fallback_time_limit,
        total_duration_seconds=total_duration,
        question_count=len(answers),
        started_at=min(answer.started_at for answer in answers),
        finished_at=max(finished_candidates) if finished_candidates else first_answer.started_at,
        practice_date=first_answer.practice_date,
    )
    db.add(paper_session)
    await db.commit()
    await db.refresh(paper_session)
    return paper_session


async def save_paper_session_analysis(
    db: AsyncSession,
    paper_session: PaperSession,
    feedback: str,
    model_name: str,
    total_duration: int
):
    """保存整套分析结果到套卷会话记录。"""
    paper_session.total_duration_seconds = total_duration
    paper_session.analysis_feedback = feedback
    paper_session.analysis_score = extract_score_from_feedback(feedback)
    paper_session.model_name = model_name
    await db.commit()
    await db.refresh(paper_session)


@router.post("", response_model=AnswerResponse)
async def create_answer(
    data: AnswerCreate,
    db: AsyncSession = Depends(get_db)
):
    """提交作答"""
    # 验证 mode
    if data.mode not in ("single", "paper"):
        raise HTTPException(status_code=400, detail="mode 必须为 single 或 paper")

    # 验证 question_id 存在性
    result = await db.execute(select(Question).where(Question.id == data.question_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="题目不存在")

    # 验证 paper 模式业务规则
    if data.mode == "paper":
        if not data.paper_session_id:
            raise HTTPException(status_code=400, detail="套卷模式需要 paper_session_id")
    elif data.paper_id or data.paper_session_id:
        raise HTTPException(status_code=400, detail="单题模式不能传入 paper_id 或 paper_session_id")

    answer = Answer(
        mode=data.mode,
        question_id=data.question_id,
        paper_id=data.paper_id,
        paper_session_id=data.paper_session_id,
        transcript=data.transcript,
        audio_url=data.audio_url,
        duration_seconds=data.duration_seconds,
        started_at=data.started_at,
        finished_at=data.finished_at,
        practice_date=data.started_at.strftime("%Y-%m-%d")
    )
    db.add(answer)
    await db.commit()
    await db.refresh(answer)
    return AnswerResponse.model_validate(answer)


@router.post("/paper-session", response_model=PaperSessionResponse)
async def save_paper_session(
    data: PaperSessionCreate,
    db: AsyncSession = Depends(get_db)
):
    """保存或更新套卷会话信息。"""
    if data.paper_id:
        result = await db.execute(select(Paper).where(Paper.id == data.paper_id))
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="套卷不存在")

    result = await db.execute(
        select(PaperSession).where(PaperSession.paper_session_id == data.paper_session_id)
    )
    paper_session = result.scalar_one_or_none()

    if not paper_session:
        paper_session = PaperSession(
            paper_session_id=data.paper_session_id,
            practice_date=data.started_at.strftime("%Y-%m-%d")
        )
        db.add(paper_session)

    paper_session.paper_id = data.paper_id
    paper_session.paper_title = data.paper_title
    paper_session.time_limit_seconds = data.time_limit_seconds
    paper_session.total_duration_seconds = data.total_duration_seconds
    paper_session.question_count = data.question_count
    paper_session.started_at = data.started_at
    paper_session.finished_at = data.finished_at
    paper_session.practice_date = data.started_at.strftime("%Y-%m-%d")

    await db.commit()
    await db.refresh(paper_session)
    return PaperSessionResponse.model_validate(paper_session)


@router.get("/{answer_id}", response_model=AnswerWithAnalysis)
async def get_answer(
    answer_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取作答详情"""
    result = await db.execute(
        select(Answer)
        .options(selectinload(Answer.analysis), selectinload(Answer.question))
        .where(Answer.id == answer_id)
    )
    answer = result.scalar_one_or_none()
    if not answer:
        raise HTTPException(status_code=404, detail="作答记录不存在")

    response = AnswerWithAnalysis.model_validate(answer)
    response.question_content = answer.question.content if answer.question else None
    return response


async def run_analysis(answer_id: int):
    """后台分析任务 - 使用独立的数据库会话"""
    async with async_session_maker() as db:
        try:
            result = await db.execute(
                select(Answer)
                .options(selectinload(Answer.question))
                .where(Answer.id == answer_id)
            )
            answer = result.scalar_one_or_none()
            if not answer:
                logger.warning(f"分析任务: 作答记录 {answer_id} 不存在")
                return

            service = AnalyzeService(db)
            analysis_result = await service.analyze_answer(
                question=answer.question.content,
                answer=answer.transcript or "",
                duration=answer.duration_seconds or 0,
                prompt_type="single_analyze"
            )

            # 从反馈中提取分数
            feedback = analysis_result["feedback"]
            score = extract_score_from_feedback(feedback)

            # 保存分析结果
            analysis = AnalysisResult(
                answer_id=answer_id,
                analysis_type="single",
                score=score,
                feedback=feedback,
                model_name=analysis_result["model_name"]
            )
            db.add(analysis)
            await db.commit()
            logger.info(f"分析任务完成: answer_id={answer_id}, score={score}")
        except Exception as e:
            logger.error(f"分析任务失败: answer_id={answer_id}, error={e}")


@router.post("/{answer_id}/analyze")
async def analyze_answer(
    answer_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """触发 AI 分析（单题）"""
    result = await db.execute(
        select(Answer).where(Answer.id == answer_id)
    )
    answer = result.scalar_one_or_none()
    if not answer:
        raise HTTPException(status_code=404, detail="作答记录不存在")

    # 检查是否已有分析结果
    result = await db.execute(
        select(AnalysisResult).where(AnalysisResult.answer_id == answer_id)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="已有分析结果")

    # 后台执行分析（不再传入 db 会话）
    background_tasks.add_task(run_analysis, answer_id)

    return {"message": "分析任务已提交", "answer_id": answer_id}


@router.get("/{answer_id}/analysis", response_model=AnalysisResultResponse)
async def get_analysis(
    answer_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取分析结果"""
    result = await db.execute(
        select(AnalysisResult).where(AnalysisResult.answer_id == answer_id)
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail="分析结果不存在或仍在处理中")
    return AnalysisResultResponse.model_validate(analysis)


@router.get("/{answer_id}/analysis/stream")
async def stream_analysis(
    answer_id: int,
    db: AsyncSession = Depends(get_db)
):
    """SSE 流式分析"""
    # 检查 Answer 是否存在
    result = await db.execute(
        select(Answer)
        .options(selectinload(Answer.question))
        .where(Answer.id == answer_id)
    )
    answer = result.scalar_one_or_none()
    if not answer:
        raise HTTPException(status_code=404, detail="作答记录不存在")

    # 检查是否已有分析结果
    result = await db.execute(
        select(AnalysisResult).where(AnalysisResult.answer_id == answer_id)
    )
    existing = result.scalar_one_or_none()
    if existing:
        async def return_existing():
            yield f"event: done\ndata: {json.dumps({'score': existing.score, 'full_content': existing.feedback}, ensure_ascii=False)}\n\n"
        return StreamingResponse(
            return_existing(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-store, no-transform",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
                "Content-Encoding": "none",
            }
        )

    # 检查是否正在分析
    if analysis_locks.get(answer_id):
        raise HTTPException(status_code=409, detail="分析正在进行中")

    analysis_locks[answer_id] = True

    async def generate():
        full_content = ""
        model_name = ""
        try:
            async with async_session_maker() as stream_db:
                service = AnalyzeService(stream_db)
                model_config = await service.get_active_model()
                if not model_config:
                    yield f"event: error\ndata: {json.dumps({'message': '未配置激活的分析模型'}, ensure_ascii=False)}\n\n"
                    return
                model_name = model_config.model_name

                async for chunk in service.analyze_answer_stream(
                    question=answer.question.content,
                    answer=answer.transcript or "",
                    duration=answer.duration_seconds or 0,
                    prompt_type="single_analyze"
                ):
                    full_content += chunk
                    yield f"event: token\ndata: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"

                # 提取分数
                score = extract_score_from_feedback(full_content)

                # 保存分析结果
                analysis = AnalysisResult(
                    answer_id=answer_id,
                    analysis_type="single",
                    score=score,
                    feedback=full_content,
                    model_name=model_name
                )
                stream_db.add(analysis)
                await stream_db.commit()

                yield f"event: done\ndata: {json.dumps({'score': score, 'full_content': full_content}, ensure_ascii=False)}\n\n"
        except asyncio.CancelledError:
            # 客户端断开，继续后台保存
            if full_content:
                asyncio.create_task(save_partial_analysis(answer_id, full_content, model_name))
        except Exception as e:
            logger.error(f"流式分析失败: answer_id={answer_id}, error={e}")
            yield f"event: error\ndata: {json.dumps({'message': str(e)}, ensure_ascii=False)}\n\n"
        finally:
            analysis_locks.pop(answer_id, None)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
            "Content-Encoding": "none",
        }
    )


async def save_partial_analysis(answer_id: int, content: str, model_name: str):
    """后台保存部分分析结果"""
    async with async_session_maker() as db:
        try:
            score = extract_score_from_feedback(content)

            analysis = AnalysisResult(
                answer_id=answer_id,
                analysis_type="single",
                score=score,
                feedback=content,
                model_name=model_name
            )
            db.add(analysis)
            await db.commit()
            logger.info(f"后台保存分析结果: answer_id={answer_id}")
        except Exception as e:
            logger.error(f"后台保存失败: answer_id={answer_id}, error={e}")


@router.post("/history-analyze")
async def analyze_history(
    data: HistoryAnalyzeRequest,
    db: AsyncSession = Depends(get_db)
):
    """历史综合分析（不保存）"""
    history_data = ""

    if data.paper_session_ids:
        result = await db.execute(
            select(PaperSession)
            .where(PaperSession.paper_session_id.in_(data.paper_session_ids))
        )
        session_map = {
            session.paper_session_id: session
            for session in result.scalars().all()
        }

        result = await db.execute(
            select(Answer)
            .options(selectinload(Answer.question), selectinload(Answer.paper))
            .where(Answer.paper_session_id.in_(data.paper_session_ids))
            .order_by(Answer.created_at)
        )
        answers = result.scalars().all()
        if not answers:
            raise HTTPException(status_code=404, detail="未找到记录")

        grouped_answers: dict[str, list[Answer]] = {}
        for answer in answers:
            session_id = answer.paper_session_id or ""
            grouped_answers.setdefault(session_id, []).append(answer)

        history_lines = []
        for session_id in data.paper_session_ids:
            session_answers = grouped_answers.get(session_id, [])
            if not session_answers:
                continue

            paper_session = session_map.get(session_id)
            title = (
                paper_session.paper_title
                if paper_session
                else (session_answers[0].paper.title if session_answers[0].paper else "套卷练习")
            )
            total_duration = (
                paper_session.total_duration_seconds
                if paper_session and paper_session.total_duration_seconds is not None
                else sum(answer.duration_seconds or 0 for answer in session_answers)
            )
            score = (
                paper_session.analysis_score
                if paper_session and paper_session.analysis_score is not None
                else "无"
            )

            question_lines = []
            for idx, answer in enumerate(session_answers, 1):
                question_lines.append(
                    f"第 {idx} 题: {answer.question.content[:60]}...\n"
                    f"作答: {(answer.transcript or '')[:120]}..."
                )

            history_lines.append(
                f"日期: {session_answers[0].practice_date}\n"
                f"套题: {title}\n"
                f"题量: {len(session_answers)}\n"
                f"总用时: {total_duration}秒\n"
                f"整体得分: {score}\n"
                f"{chr(10).join(question_lines)}\n"
                f"---"
            )

        history_data = "\n".join(history_lines)
    else:
        if not data.answer_ids:
            raise HTTPException(status_code=400, detail="请选择至少一条记录")

        result = await db.execute(
            select(Answer)
            .options(selectinload(Answer.analysis), selectinload(Answer.question))
            .where(Answer.id.in_(data.answer_ids))
            .order_by(Answer.created_at)
        )
        answers = result.scalars().all()

        if not answers:
            raise HTTPException(status_code=404, detail="未找到记录")

        history_lines = []
        for answer in answers:
            score = answer.analysis.score if answer.analysis else "无"
            history_lines.append(
                f"日期: {answer.practice_date}\n"
                f"题目: {answer.question.content[:100]}...\n"
                f"作答: {(answer.transcript or '')[:200]}...\n"
                f"得分: {score}\n"
                f"---"
            )

        history_data = "\n".join(history_lines)

    service = AnalyzeService(db)
    try:
        result = await service.analyze_history(
            history_data=history_data,
            prompt_type=data.analysis_type
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"feedback": result["feedback"], "model_name": result["model_name"]}


@router.post("/paper-analyze")
async def analyze_paper_session(
    data: PaperAnalyzeRequest,
    db: AsyncSession = Depends(get_db)
):
    """套卷整体分析。"""
    if not data.paper_session_id:
        raise HTTPException(status_code=400, detail="请提供套卷会话ID")

    paper_session_result = await db.execute(
        select(PaperSession).where(PaperSession.paper_session_id == data.paper_session_id)
    )
    paper_session = paper_session_result.scalar_one_or_none()

    result = await db.execute(
        select(Answer)
        .options(selectinload(Answer.question), selectinload(Answer.paper))
        .where(Answer.paper_session_id == data.paper_session_id)
        .order_by(Answer.created_at)
    )
    answers = result.scalars().all()

    if not answers:
        raise HTTPException(status_code=404, detail="未找到套卷作答记录")

    paper_session = await ensure_paper_session_record(
        db,
        data.paper_session_id,
        answers,
        fallback_time_limit=paper_session.time_limit_seconds if paper_session else None
    )
    paper_content, time_details, total_duration, analysis_time_limit = build_paper_analysis_payload(
        answers,
        paper_session.time_limit_seconds
    )

    service = AnalyzeService(db)
    try:
        result = await service.analyze_paper(
            paper_content=paper_content,
            time_details=time_details,
            total_time=analysis_time_limit
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await save_paper_session_analysis(
        db,
        paper_session,
        result["feedback"],
        result["model_name"],
        total_duration
    )

    return {"feedback": result["feedback"], "model_name": result["model_name"]}


@router.get("/paper-analyze/stream/{session_id}")
async def stream_paper_analysis(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """套卷流式分析（SSE）"""
    if not session_id:
        raise HTTPException(status_code=400, detail="请提供套卷会话ID")

    # 检查是否正在分析
    if paper_analysis_locks.get(session_id):
        raise HTTPException(status_code=409, detail="分析正在进行中")

    # 查询该会话的所有作答
    result = await db.execute(
        select(Answer)
        .options(selectinload(Answer.question), selectinload(Answer.paper))
        .where(Answer.paper_session_id == session_id)
        .order_by(Answer.created_at)
    )
    answers = result.scalars().all()

    if not answers:
        raise HTTPException(status_code=404, detail="未找到套卷作答记录")

    paper_session_result = await db.execute(
        select(PaperSession).where(PaperSession.paper_session_id == session_id)
    )
    paper_session = paper_session_result.scalar_one_or_none()
    paper_session = await ensure_paper_session_record(
        db,
        session_id,
        answers,
        fallback_time_limit=paper_session.time_limit_seconds if paper_session else None
    )
    paper_content, time_details, total_duration, analysis_time_limit = build_paper_analysis_payload(
        answers,
        paper_session.time_limit_seconds
    )

    paper_analysis_locks[session_id] = True

    async def generate():
        full_content = ""
        model_name = ""
        try:
            async with async_session_maker() as stream_db:
                service = AnalyzeService(stream_db)
                model_config = await service.get_active_model()
                if not model_config:
                    yield f"event: error\ndata: {json.dumps({'message': '未配置激活的分析模型'}, ensure_ascii=False)}\n\n"
                    return
                model_name = model_config.model_name

                async for chunk in service.analyze_paper_stream(
                    paper_content=paper_content,
                    time_details=time_details,
                    total_time=analysis_time_limit
                ):
                    full_content += chunk
                    yield f"event: token\ndata: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"

                stream_session_result = await stream_db.execute(
                    select(PaperSession).where(PaperSession.paper_session_id == session_id)
                )
                stream_paper_session = stream_session_result.scalar_one_or_none()
                if stream_paper_session:
                    await save_paper_session_analysis(
                        stream_db,
                        stream_paper_session,
                        full_content,
                        model_name,
                        total_duration
                    )

                yield f"event: done\ndata: {json.dumps({'full_content': full_content}, ensure_ascii=False)}\n\n"
        except asyncio.CancelledError:
            logger.info(f"套卷分析被取消: session_id={session_id}")
        except Exception as e:
            logger.error(f"套卷流式分析失败: session_id={session_id}, error={e}")
            yield f"event: error\ndata: {json.dumps({'message': str(e)}, ensure_ascii=False)}\n\n"
        finally:
            paper_analysis_locks.pop(session_id, None)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
            "Content-Encoding": "none",
        }
    )
