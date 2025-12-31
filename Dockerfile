# SecretFlow 隐私计算后端 Docker 镜像
# 基于 SecretFlow 生产模式的 Celery Worker

FROM secretflow/secretflow-anolis8:1.12.0b0

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV CELERY_APP=src.celery_app:celery_app

# 创建必要的目录
RUN mkdir -p /app/data /app/logs /tmp/secretflow

# 安装系统依赖
RUN yum update -y && \
    yum install -y procps-ng net-tools telnet && \
    yum clean all

# 复制项目文件
COPY pyproject.toml /app/
COPY src/ /app/src/
COPY scripts/ /app/scripts/
COPY docker/ /app/docker/

# 安装 Python 依赖
RUN pip install --no-cache-dir -e /app

# 创建非 root 用户
RUN groupadd -r secretflow && \
    useradd -r -g secretflow -m -s /bin/bash secretflow && \
    chown -R secretflow:secretflow /app /tmp/secretflow

# 切换到非 root 用户
USER secretflow

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import redis; r=redis.Redis(host='${REDIS_HOST}', port=${REDIS_PORT}); r.ping()" || exit 1

# 暴露端口
EXPOSE 9394

# 设置启动命令
CMD ["python", "-m", "src.worker"]
