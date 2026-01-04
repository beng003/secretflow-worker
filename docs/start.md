

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
celery -A src.celery_app call tasks.secretflow.local_test.local_psi_test
celery -A src.celery_app call tasks.secretflow.health_check.health_check_task
# 查看任务结果
celery -A src.celery_app result <task_id>
```

### 3. requirements.txt 生成
```bash
uv export --format requirements-txt --output-file requirements.txt
```

### 4. Dockerfile

```bash
# 不使用缓存重新构建
docker build --no-cache -t secretflow-work .
# 指定构建上下文和Dockerfile位置
docker build -f docker/Dockerfile -t secretflow-work .
# 查看构建过程详细信息
docker build -t secretflow-work . --progress=plain
```