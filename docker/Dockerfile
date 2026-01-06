# SecretFlow 隐私计算后端 Docker 镜像
# 使用 pip 简化依赖安装

FROM python:3.10.16-slim

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
    # SecretFlow 特定依赖
    libomp-dev \
    libssl-dev \
    libffi-dev \
    # Python 开发依赖
    python3-dev \
    # 清理缓存
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 升级 pip 到最新版本
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# 复制 requirements.txt 并安装 Python 依赖
# 先复制 requirements.txt 以利用 Docker 层缓存
COPY requirements.txt /app/
# 安装SecretFlow Worker专用依赖
RUN pip install --no-cache-dir --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制项目源代码
COPY src/ /app/src/
COPY scripts/ /app/scripts/
COPY docker/ /app/docker/
COPY main.py /app/
COPY .env.secretflow /app/

# 设置脚本执行权限
RUN chmod +x /app/scripts/*.sh

# 创建非 root 用户
RUN groupadd -r secretflow && \
    useradd -r -g secretflow -m -s /bin/bash secretflow && \
    chown -R secretflow:secretflow /app /tmp/secretflow

# 切换到非 root 用户
USER secretflow

# 使用入口脚本启动
ENTRYPOINT ["/app/scripts/entrypoint.sh"]

# 健康检查（检查Worker进程是否运行）
HEALTHCHECK --interval=60s --timeout=30s --start-period=60s --retries=3 \
    CMD pgrep -f "python src/worker.py" || exit 1
