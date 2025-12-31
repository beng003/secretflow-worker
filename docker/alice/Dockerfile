FROM python:3.10-slim

# 设置工作目录
WORKDIR /workspace

# 更新包管理器并安装系统依赖
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    vim \
    net-tools \
    build-essential \
    pkg-config \
    cmake \
    libssl-dev \
    libffi-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# 创建用户和数据目录
RUN useradd -m -s /bin/bash secretflow && \
    mkdir -p /data/alice /scripts && \
    chmod 755 /data/alice /scripts && \
    chown -R secretflow:secretflow /data/alice /scripts /workspace

# 安装 Python 包（不包含 Ray）
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir \
        pandas==1.5.3 \
        numpy==1.26.4 \
        scikit-learn==1.5.2 \
        grpcio==1.51.3 \
        protobuf==4.25.8 \
        cloudpickle==3.1.2 \
        cryptography==46.0.3

# 安装 SecretFlow（允许预发布版本）
RUN pip install --no-cache-dir --pre secretflow

# 切换到非root用户
USER secretflow

# 暴露端口
EXPOSE 8000 9394 12945 8265

# 设置环境变量
ENV RAY_DISABLE_IMPORT_WARNING=1
ENV RAY_DEDUP_LOGS=0
ENV PYTHONPATH=/workspace
ENV PATH=/home/secretflow/.local/bin:$PATH

# 启动命令将在docker-compose中定义
