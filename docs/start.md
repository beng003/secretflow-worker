

## 🔧 Celery服务启动

### 1. 基本启动命令

#### 启动Worker进程
```bash
# 进入src目录
cd src

# 启动默认队列Worker
celery -A src.celery_app worker --loglevel=info

# 启动指定队列Worker
celery -A src.celery_app worker --loglevel=info -Q default

# 启动多个队列Worker
celery -A src.celery_app worker --loglevel=info -Q default,web_queue
celery -A src.celery_app worker --loglevel=info -Q secretflow_queue

# 后台启动Worker
celery -A src.celery_app worker --loglevel=info --detach
```

#### 启动Beat调度器（定时任务）
```bash
# 启动Beat调度器
celery -A src.celery_app beat --loglevel=info

# 后台启动Beat
celery -A src.celery_app beat --loglevel=info --detach

# 使用数据库存储调度信息
celery -A src.celery_app beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

### 2. 命令行发起任务
#### 使用celery call命令
```bash
# 发起 hello 任务
celery -A src.celery_app call tasks.secretflow.hello.hello_task

# 发起网络诊断任务
celery -A src.celery_app call tasks.web.diagnostics.run_network_sync --kwargs='{"node_id":"node_001","test_types":["ping","dns"]}'

# 查看任务结果
celery -A src.celery_app result <task_id>
```