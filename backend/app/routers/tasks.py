from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.schemas import DeliveryMode, TaskStatus
from app.services.task_store import get_task_store

router = APIRouter(prefix="/api", tags=["tasks"])


class TaskProgressResponse(BaseModel):
    taskId: str
    status: TaskStatus
    progress: float
    message: str
    downloadUrl: str | None = None
    filename: str | None = None
    error: str | None = None
    delivery: DeliveryMode | None = None


@router.get("/tasks/{task_id}", response_model=TaskProgressResponse)
def get_task(task_id: str) -> TaskProgressResponse:
    task = get_task_store().get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="找不到此任務")
    return TaskProgressResponse(
        taskId=task.taskId,
        status=task.status,
        progress=task.progress,
        message=task.message,
        downloadUrl=task.downloadUrl,
        filename=task.filename,
        error=task.error,
        delivery=task.delivery,
    )
