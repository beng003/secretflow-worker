# Celery 异常处理最佳实践

## 问题背景

后端 `EventReceiver` 查询任务状态时报错：
```
Exception information must include the exception type
```

## 根本原因

在 `on_failure` 回调中调用 `self.update_state(state="FAILURE", meta={...})` 时，如果 `meta` 中包含了异常对象或格式不正确的异常信息，会导致 Celery 在序列化/反序列化时出错。

## 解决方案

### ✅ 正确做法：只在 meta 中使用字符串

```python
def on_failure(self, exc, task_id, args, kwargs, einfo):
    """任务失败时的回调"""
    task_params = args[0] if args else kwargs.get("task_params", {})
    
    # ✅ 正确：只使用字符串形式的错误信息
    self.update_state(
        state="FAILURE",
        meta={
            "task_id": task_params.get("task_id", "unknown"),
            "subtask_id": task_params.get("subtask_id", "unknown"),
            "execution_id": task_params.get("execution_id", "unknown"),
            "error_message": str(exc),           # ✅ 字符串
            "error_type": type(exc).__name__,    # ✅ 字符串
            "failed_at": datetime.now().isoformat(),
        },
    )
```

### ❌ 错误做法：在 meta 中包含异常对象

```python
def on_failure(self, exc, task_id, args, kwargs, einfo):
    # ❌ 错误：包含异常对象
    self.update_state(
        state="FAILURE",
        meta={
            "exception": exc,              # ❌ 异常对象无法正确序列化
            "error": str(exc),
            "exc_info": einfo,             # ❌ 异常信息对象
        },
    )
```

## 为什么需要在 on_failure 中手动设置状态？

虽然 Celery 会自动设置 `FAILURE` 状态，但**自动设置的状态不包含自定义业务字段**：

### Celery 自动设置的 FAILURE 状态

```python
{
    "status": "FAILURE",
    "result": {
        "exc_type": "ValueError",
        "exc_message": ["error message"],
        # ... 只有异常相关信息
    }
}
```

### 我们需要的 FAILURE 状态

```python
{
    "status": "FAILURE",
    "result": {
        "task_id": "123",              # ✅ 业务字段
        "subtask_id": "456",           # ✅ 业务字段
        "execution_id": "789",         # ✅ 业务字段
        "error_message": "...",        # ✅ 错误信息
        "error_type": "ValueError",    # ✅ 错误类型
        "stage": "task_failed_final",  # ✅ 失败阶段
        "failed_at": "2026-02-01...",  # ✅ 失败时间
    }
}
```

## 完整示例

### 1. on_failure 回调

```python
def on_failure(self, exc, task_id, args, kwargs, einfo):
    """任务失败时的回调"""
    task_params = args[0] if args else kwargs.get("task_params", {})
    execution_id = task_params.get("execution_id", "unknown")

    # 记录详细日志
    logger.error(
        "SecretFlow任务失败: celery_task_id=%s, task_id=%s, subtask_id=%s, "
        "execution_id=%s, error_type=%s, error=%s, retries=%s/%s",
        task_id,
        task_params.get("task_id", "unknown"),
        task_params.get("subtask_id", "unknown"),
        execution_id,
        type(exc).__name__,
        str(exc),
        self.request.retries,
        self.max_retries,
        exc_info=True,
    )

    # 更新状态，包含自定义业务字段
    try:
        self.update_state(
            state="FAILURE",
            meta={
                "stage": "task_failed_final",
                "task_id": task_params.get("task_id", "unknown"),
                "subtask_id": task_params.get("subtask_id", "unknown"),
                "execution_id": execution_id,
                "celery_task_id": task_id,
                "error_message": str(exc),  # ✅ 只使用字符串
                "error_type": type(exc).__name__,
                "retries_exhausted": self.request.retries >= self.max_retries,
                "failed_at": datetime.now().isoformat(),
            },
        )
    except Exception as update_error:
        # 如果状态更新失败，记录日志但不影响主流程
        logger.warning(
            f"更新失败状态时出错: {update_error}, 原始异常: {exc}"
        )
```

### 2. 主任务函数中的异常处理

```python
def execute_secretflow_celery_task(self, task_params):
    try:
        result = execute_secretflow_task(...)
        return result
        
    except SoftTimeLimitExceeded:
        # 超时异常
        logger.error("任务超时...")
        # 直接抛出，让 on_failure 处理
        raise
        
    except (ClusterInitError, DeviceConfigError) as e:
        # 可重试的错误
        logger.warning("遇到可重试错误...")
        raise self.retry(exc=e, countdown=60)
        
    except Exception as e:
        # 其他错误
        logger.error("任务执行失败...", exc_info=True)
        # 直接抛出，让 on_failure 处理
        raise
```

## 关键要点

### ✅ 应该做的

1. **在 `on_failure` 中设置自定义业务字段**
   - `task_id`, `subtask_id`, `execution_id` 等业务标识
   - `stage` 失败阶段
   - `failed_at` 失败时间

2. **只使用字符串形式的错误信息**
   - `error_message`: `str(exc)`
   - `error_type`: `type(exc).__name__`

3. **添加异常处理保护**
   - 用 `try-except` 包裹 `update_state` 调用
   - 避免状态更新失败影响主流程

### ❌ 不应该做的

1. **不要在 meta 中包含异常对象**
   - ❌ `"exception": exc`
   - ❌ `"exc_info": einfo`

2. **不要在主任务函数中手动设置 FAILURE 状态**
   - 直接 `raise` 异常
   - 让 `on_failure` 统一处理

3. **不要重复设置状态**
   - 只在 `on_failure` 中设置一次
   - 避免格式冲突

## 后端查询任务状态

### 使用 AsyncResult 查询

```python
from celery.result import AsyncResult

result = AsyncResult(celery_task_id)

# 查询状态
print(result.state)  # 'PENDING', 'PROGRESS', 'SUCCESS', 'FAILURE'

# 查询详细信息
if result.state == 'FAILURE':
    info = result.info
    print(f"任务ID: {info.get('task_id')}")
    print(f"执行ID: {info.get('execution_id')}")
    print(f"错误类型: {info.get('error_type')}")
    print(f"错误信息: {info.get('error_message')}")
    print(f"失败时间: {info.get('failed_at')}")
```

### 使用 EventReceiver 监听

```python
from celery import Celery

app = Celery('tasks', broker='redis://localhost:6379/0')

def on_event(event):
    if event['type'] == 'task-failed':
        task_id = event['uuid']
        # 查询详细状态
        result = AsyncResult(task_id)
        info = result.info
        
        # 处理失败事件
        print(f"任务失败: {info.get('task_id')}")
        print(f"错误: {info.get('error_message')}")

# 监听事件
with app.connection() as connection:
    recv = app.events.Receiver(connection, handlers={
        'task-failed': on_event,
    })
    recv.capture(limit=None, timeout=None)
```

## 验证方法

### 1. 提交一个会失败的任务

```python
from celery_app import celery_app

result = celery_app.send_task(
    'tasks.secretflow.execute_task',
    args=[{
        "task_id": "test_123",
        "subtask_id": "sub_456",
        "execution_id": "exec_789",
        # ... 其他参数
    }]
)
```

### 2. 查询失败状态

```python
import time
from celery.result import AsyncResult

result = AsyncResult(celery_task_id)

while not result.ready():
    time.sleep(2)

if result.failed():
    info = result.info
    print("任务失败信息:")
    print(f"  task_id: {info.get('task_id')}")
    print(f"  subtask_id: {info.get('subtask_id')}")
    print(f"  execution_id: {info.get('execution_id')}")
    print(f"  error_type: {info.get('error_type')}")
    print(f"  error_message: {info.get('error_message')}")
    print(f"  failed_at: {info.get('failed_at')}")
```

### 3. 检查后端日志

应该**不再**出现以下错误：
```
❌ Exception information must include the exception type
```

应该能正常查询到失败信息：
```
✅ 任务状态更新: celery_task_id=xxx, state=FAILURE
✅ 任务失败信息: task_id=123, error=ValueError: ...
```

## 总结

- ✅ **保留** `on_failure` 中的 `update_state` 调用
- ✅ **只使用字符串**形式的错误信息（`str(exc)`, `type(exc).__name__`）
- ✅ **包含自定义业务字段**（`task_id`, `subtask_id`, `execution_id` 等）
- ✅ **添加异常处理**保护状态更新
- ❌ **不要包含异常对象**或复杂的异常信息结构

这样既能保留自定义业务字段，又能避免异常序列化格式冲突。
