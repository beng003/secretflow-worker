# SecretFlow 隐私计算后端

基于 SecretFlow 生产模式的分布式隐私计算后端服务，使用 Celery Worker 架构，支持 Docker 容器化部署。

## 🎯 项目特性

- **🔒 隐私计算**: 支持 PSI、联邦学习、安全聚合等隐私计算算法
- **🚀 生产级部署**: 基于 SecretFlow 生产模式，使用内置 Ray 集群
- **📦 容器化**: 完整的 Docker 和 Kubernetes 部署支持
- **⚡ 分布式任务**: Celery + Redis 实现可扩展的分布式任务队列
- **📊 监控运维**: 集成 Flower、Redis Commander 等监控工具
- **🔧 配置灵活**: 基于环境变量的配置管理，支持多环境部署

## 🏗 系统架构

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Alice 节点    │    │   Bob 节点      │    │   Charlie 节点  │
│                 │    │                 │    │                 │
│ ┌─────────────┐ │    │ ┌─────────────┐ │    │ ┌─────────────┐ │
│ │Celery Worker│ │    │ │Celery Worker│ │    │ │Celery Worker│ │
│ │SecretFlow   │ │    │ │SecretFlow   │ │    │ │SecretFlow   │ │
│ │Ray Cluster  │ │    │ │Ray Cluster  │ │    │ │Ray Cluster  │ │
│ └─────────────┘ │    │ └─────────────┘ │    │ └─────────────┘ │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │              ┌────────┴────────┐             │
         └──────────────►│  Redis 消息队列  │◄──────────────┘
                        │  结果存储后端    │
                        └─────────────────┘
                                 │
                        ┌────────┴────────┐
                        │   监控服务       │
                        │ Flower + Redis  │
                        │   Commander     │
                        └─────────────────┘
```

## 📋 系统要求

### 硬件要求
- **CPU**: 最少 2 核，推荐 4 核以上
- **内存**: 最少 4GB，推荐 8GB 以上
- **存储**: 最少 20GB 可用空间
- **网络**: 节点间需要稳定的网络连接

### 软件要求
- **操作系统**: Linux (推荐 Ubuntu 20.04+, CentOS 8+)
- **Docker**: 20.10+ 
- **Docker Compose**: 2.0+
- **Python**: 3.10+ (用于开发环境)

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone <repository-url>
cd secretflow_test
```

### 2. 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑配置文件
nano .env
```

关键配置项：

```env
# 节点标识 (alice, bob, charlie 等)
NODE_ID=alice
NODE_IP=localhost

# Redis 配置
REDIS_HOST=localhost
REDIS_PORT=6379

# 集群配置
CLUSTER_CONFIG='{"alice": "localhost:9394", "bob": "localhost:9395"}'
CLUSTER_NODES=localhost:9394,localhost:9395

# 安全令牌 (生产环境必须修改)
SECURITY_TOKEN=your-security-token-here
```

### 3. 启动服务

#### Docker Compose 部署 (推荐)

```bash
# 一键部署 (包含 Alice, Bob 双节点 + Redis + 监控)
./scripts/deploy.sh -m docker -e development

# 或者手动启动
cd docker
docker-compose up -d
```

#### 单节点开发模式

```bash
# 启动 Redis
docker run -d --name redis -p 6379:6379 redis:7-alpine

# 安装依赖
pip install -e .

# 启动 Celery Worker
python -m src.worker
```

### 4. 验证部署

访问监控面板：
- **Flower (Celery 监控)**: http://localhost:5555
- **Redis Commander**: http://localhost:8081

查看服务状态：

```bash
# 查看容器状态
docker-compose ps

# 查看服务日志
docker-compose logs -f
```

## 🛠 使用方法

### Ray 集群管理

SecretFlow 要求手动启动 Ray 集群。本项目提供了集群管理脚本：

```bash
# 在头节点启动 Ray 集群
./scripts/ray_cluster.sh --type head --node-ip 192.168.1.100 start

# 在工作节点连接到集群
./scripts/ray_cluster.sh --type worker --head-ip 192.168.1.100 --node-ip 192.168.1.101 start

# 查看集群状态
./scripts/ray_cluster.sh status

# 停止集群
./scripts/ray_cluster.sh stop
```

### 提交隐私计算任务

通过 Python 客户端提交任务：

```python
from celery import Celery

# 连接到 Celery
app = Celery('secretflow_backend', broker='redis://localhost:6379/0')

# 提交 PSI 任务
task_config = {
    "task_id": "psi_demo_001",
    "parties": ["alice", "bob"],
    "data_config": {
        "input_file": "/app/data/alice_data.csv",
        "key_columns": ["id", "phone"],
        "protocol": "ECDH_PSI_2PC"
    },
    "output_config": {
        "output_path": "/app/data/output/"
    }
}

# 异步提交任务
result = app.send_task(
    'tasks.privacy_computing.psi_intersection',
    args=[task_config]
)

# 获取结果
print(f"任务 ID: {result.id}")
print(f"任务结果: {result.get(timeout=3600)}")
```

### 支持的隐私计算算法

| 算法类型 | 任务名称 | 描述 |
|---------|----------|------|
| **隐私求交** | `psi_intersection` | 多方隐私集合求交 |
| **联邦学习** | `federated_learning` | 分布式机器学习训练 |
| **安全聚合** | `secure_aggregation` | 多方安全计算聚合 |

## 🔧 配置说明

### 环境变量配置

完整的环境变量列表参见 `.env.example` 文件。主要配置项：

#### 节点配置
```env
NODE_ID=alice                    # 节点唯一标识
NODE_IP=localhost                # 节点 IP 地址
NODE_PORT=9394                   # 节点端口
```

#### Redis 配置
```env
REDIS_HOST=localhost             # Redis 主机
REDIS_PORT=6379                  # Redis 端口
REDIS_PASSWORD=                  # Redis 密码(可选)
```

#### Celery 配置
```env
MAX_CONCURRENT_TASKS=4           # 最大并发任务数
TASK_TIMEOUT=3600                # 任务超时时间(秒)
```

#### 安全配置
```env
SECURITY_TOKEN=your-token        # 安全认证令牌
SSL_CERT_PATH=/path/to/cert      # SSL 证书路径
SSL_KEY_PATH=/path/to/key        # SSL 私钥路径
```

### Docker 配置

项目包含以下 Docker 服务：

| 服务 | 端口 | 描述 |
|------|------|------|
| `secretflow-worker-alice` | 9394 | Alice 节点 |
| `secretflow-worker-bob` | 9395 | Bob 节点 |
| `redis` | 6379 | 消息队列和结果存储 |
| `flower` | 5555 | Celery 监控面板 |
| `redis-commander` | 8081 | Redis 管理界面 |

## 📊 监控运维

### 健康检查

每个节点自动执行健康检查任务：

```python
# 手动触发健康检查
from src.tasks.health_check import node_health_check
result = node_health_check.delay()
print(result.get())
```

### 日志管理

```bash
# 查看特定服务日志
docker-compose logs -f secretflow-worker-alice

# 查看所有服务日志
docker-compose logs -f

# 查看 Celery Worker 日志
tail -f /app/logs/worker.log
```

### 性能监控

通过 Flower 面板监控：
- 任务执行状态和历史
- Worker 节点状态
- 队列堆积情况
- 系统资源使用

访问 http://localhost:5555 查看监控面板。

## 🚢 部署指南

### 生产环境部署

1. **环境准备**
```bash
# 创建生产配置
cp .env.example .env.production

# 编辑生产配置
vim .env.production
```

2. **安全配置**
```bash
# 生成安全令牌
openssl rand -hex 32

# 生成 SSL 证书 (如果需要)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout server.key -out server.crt
```

3. **部署执行**
```bash
# 生产环境部署
./scripts/deploy.sh -m docker -e production -n 3 --force
```

### Kubernetes 部署

```bash
# K8s 部署
./scripts/deploy.sh -m kubernetes -e production -n 5

# 查看部署状态
kubectl get pods -n secretflow

# 查看服务日志
kubectl logs -f deployment/secretflow-backend -n secretflow
```

### 多节点集群部署

对于跨服务器的多节点部署：

1. **网络配置**: 确保节点间网络互通
2. **防火墙设置**: 开放必要端口 (9394, 10001, 等)
3. **时间同步**: 配置 NTP 服务确保时间同步
4. **存储配置**: 配置共享存储或分布式文件系统

## 🔍 故障排除

### 常见问题

#### 1. Redis 连接失败
```bash
# 检查 Redis 服务状态
docker-compose ps redis

# 检查网络连通性
docker exec secretflow-worker-alice ping redis
```

#### 2. Ray 集群连接问题
```bash
# 检查 Ray 进程
./scripts/ray_cluster.sh status

# 重启 Ray 集群
./scripts/ray_cluster.sh restart
```

#### 3. 任务执行失败
```bash
# 查看详细错误日志
docker-compose logs secretflow-worker-alice

# 检查任务队列状态
# 访问 http://localhost:5555
```

#### 4. 内存不足
```bash
# 调整 Docker 内存限制
# 编辑 docker-compose.yml 中的 memory 配置

# 减少并发任务数
# 修改 .env 中的 MAX_CONCURRENT_TASKS
```

### 调试模式

开启详细日志：

```env
# 在 .env 文件中设置
LOG_LEVEL=DEBUG
DEBUG=true
```

## 🤝 开发指南

### 项目结构

```
secretflow_test/
├── src/                          # 源代码
│   ├── config/                   # 配置管理
│   │   ├── settings.py          # 环境变量配置
│   │   └── __init__.py
│   ├── tasks/                    # Celery 任务
│   │   ├── privacy_computing.py # 隐私计算任务
│   │   ├── health_check.py      # 健康检查任务
│   │   └── __init__.py
│   ├── utils/                    # 工具类
│   │   ├── logger.py            # 日志工具
│   │   └── __init__.py
│   ├── celery_app.py            # Celery 应用配置
│   ├── worker.py                # Worker 主入口
│   └── __init__.py
├── docker/                       # Docker 配置
│   ├── docker-compose.yml       # 服务编排
│   └── .env.example             # 环境变量模板
├── scripts/                      # 脚本工具
│   ├── deploy.sh                # 部署脚本
│   └── ray_cluster.sh           # Ray 集群管理
├── Dockerfile                    # Docker 镜像构建
├── pyproject.toml               # Python 项目配置
└── README.md                    # 项目文档
```

### 添加新的隐私计算算法

1. **创建任务函数**
```python
# 在 src/tasks/privacy_computing.py 中添加
@celery_app.task(bind=True, name="tasks.privacy_computing.new_algorithm")
def new_algorithm(self, task_config):
    # 实现算法逻辑
    pass
```

2. **注册任务**
```python
# 在 src/celery_app.py 的 include 列表中添加任务模块
```

3. **添加配置验证**
```python
# 验证任务配置的完整性和有效性
required_keys = ["param1", "param2", "data_config"]
for key in required_keys:
    if key not in task_config:
        raise ValueError(f"缺少必需的配置参数: {key}")
```

### 测试指南

```bash
# 运行单元测试
python -m pytest tests/

# 运行集成测试
python -m pytest tests/integration/

# 测试覆盖率
coverage run -m pytest
coverage report
```

## 📝 许可证

本项目采用 [MIT License](LICENSE) 许可证。

## 🙋‍♂️ 支持

如有问题或建议，请：

1. 查阅本文档的故障排除部分
2. 搜索 [Issues](../../issues) 中的相关问题
3. 创建新的 Issue 并提供详细信息

---

**⚡ SecretFlow 隐私计算后端 - 让隐私计算更简单、更安全、更高效！**