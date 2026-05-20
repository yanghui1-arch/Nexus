# Celery worker
The worker is for agent execution. Two tasks are avaliable - coding and pm.

# Notice
推荐warm shutdown. 终止celery worker的时候等待任务完成. 不推荐cold shutdown, 这会导致任务异常失败.
