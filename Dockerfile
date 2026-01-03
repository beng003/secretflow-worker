# SecretFlow 隐私计算后端 Docker 镜像
# 基于标准 Python 镜像自建 SecretFlow 环境

FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV CELERY_APP=src.celery_app:celery_app
ENV DEBIAN_FRONTEND=noninteractive

# 创建必要的目录
RUN mkdir -p /app/data /app/logs /tmp/secretflow

# 安装系统依赖（SecretFlow 编译依赖）
RUN apt-get update && apt-get install -y \
    # 基础工具
    build-essential \
    cmake \
    git \
    curl \
    wget \
    unzip \
    # 编译依赖
    gcc \
    g++ \
    make \
    libc6-dev \
    # 网络工具
    procps \
    net-tools \
    telnet \
    # SecretFlow 特定依赖
    libomp-dev \
    libssl-dev \
    libffi-dev \
    # Python 开发依赖
    python3-dev \
    python3-pip \
    # 清理缓存
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv 包管理器
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    mv /root/.cargo/bin/uv /usr/local/bin/uv

# 配置 uv 环境变量
ENV UV_CACHE_DIR=/tmp/uv-cache
ENV UV_LINK_MODE=copy

# 创建 uv 缓存目录
RUN mkdir -p $UV_CACHE_DIR

# 复制项目配置文件
COPY pyproject.toml /app/

# 使用 uv 创建虚拟环境并安装依赖
# 这比 pip 更快且依赖解析更准确
RUN cd /app && \
    uv venv /app/.venv && \
    echo "source /app/.venv/bin/activate" >> /etc/bash.bashrc

# 激活虚拟环境
ENV PATH="/app/.venv/bin:$PATH"
ENV VIRTUAL_ENV="/app/.venv"

# 复制项目源代码
COPY src/ /app/src/
COPY scripts/ /app/scripts/
COPY docker/ /app/docker/

# 使用 uv 安装所有依赖
# uv 会自动读取 pyproject.toml 并安装所有依赖
RUN cd /app && \
    uv sync --frozen --no-dev

# 清理 uv 缓存以减小镜像体积
RUN rm -rf $UV_CACHE_DIR

# 创建非 root 用户
RUN groupadd -r secretflow && \
    useradd -r -g secretflow -m -s /bin/bash secretflow && \
    chown -R secretflow:secretflow /app /tmp/secretflow

# 切换到非 root 用户
USER secretflow

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import redis; r=redis.Redis(host='${REDIS_HOST:-localhost}', port=${REDIS_PORT:-6379}); r.ping()" || exit 1

# 暴露端口
EXPOSE 9394

# 设置启动命令
CMD ["python", "-m", "src.worker"]
