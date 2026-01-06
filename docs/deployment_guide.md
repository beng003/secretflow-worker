# SecretFlow生产环境部署指南

## 📋 文档信息

- **版本**：v2.0
- **网络模式**：Host Network
- **更新时间**：2026年1月6日

---

## 🎯 部署概述

本指南介绍如何在生产环境中部署SecretFlow Worker节点，使用Host网络模式以获得最佳性能和最简配置。

### 架构特点

- ✅ **Host网络模式**：无NAT转换，性能最优
- ✅ **Ray命令行启动**：避免Python API兼容性问题
- ✅ **进程独立管理**：Ray和Worker独立运行，互不影响
- ✅ **配置简单清晰**：环境变量配置，易于理解和维护

---

## 📦 前置要求

### 系统要求

- **操作系统**：Linux (推荐Ubuntu 20.04+或CentOS 7+)
- **Docker**：20.10+
- **Docker Compose**：2.0+
- **内存**：建议8GB+
- **CPU**：建议4核+
- **磁盘**：建议50GB+

### 网络要求

- 节点间需要能够直接通信
- 防火墙需要开放必要端口
- 建议使用固定IP地址

### 端口规划

**单节点端口使用**：
- Redis: 60379
- Ray GCS: 61379
- SecretFlow: 19000-19009
- SPU: 19500-19509
- HEU: 19800-19809
- Celery监控: 8088

**多节点端口规划**：
- 节点1: SF 19000-19009, SPU 19500-19509, HEU 19800-19809
- 节点2: SF 19100-19109, SPU 19600-19609, HEU 19859-19899
- 节点3: SF 19200-19209, SPU 19700-19709, HEU 19900-19909

---

## 🚀 快速开始

### 1. 准备配置文件

```bash
# 进入项目目录
cd /path/to/secretflow_test

# 从模板创建生产配置
cp config/production.env.template .env.production

# 编辑配置文件
vim .env.production
```

### 2. 修改关键配置

编辑`.env.production`，至少修改以下配置：

```bash
# 节点标识
NODE_ID=node1

# 节点IP（宿主机真实IP）
NODE_IP=192.168.1.10

# Ray节点类型（head或worker）
RAY_NODE_TYPE=head

# Ray头节点地址（工作节点需要指向头节点）
RAY_HEAD_ADDRESS=192.168.1.10:61379
```

### 3. 一键部署

```bash
# 执行部署脚本
bash scripts/deploy.sh
```

部署脚本会自动完成：
- ✅ 检查配置文件
- ✅ 检查端口占用
- ✅ 停止旧容器
- ✅ 构建Docker镜像
- ✅ 启动服务
- ✅ 验证部署状态

---

## 📝 详细部署步骤

### 单节点部署

#### 步骤1：准备环境

```bash
# 检查Docker版本
docker --version
docker compose version

# 检查端口占用
netstat -tuln | grep -E "60379|61379|19000"
```

#### 步骤2：配置节点

使用`config/node1.env`作为参考：

```bash
cp config/node1.env .env.production
vim .env.production
```

关键配置项：
- `NODE_ID`: 节点唯一标识
- `NODE_IP`: 宿主机IP地址
- `RAY_NODE_TYPE`: 设置为`head`
- `RAY_HEAD_ADDRESS`: 指向自己

#### 步骤3：构建镜像

```bash
docker build -f docker/Dockerfile -t secretflow-worker:latest .
```

#### 步骤4：启动服务

```bash
docker compose -f docker/docker-compose.production.yml \
    --env-file .env.production up -d
```

#### 步骤5：验证部署

```bash
# 查看容器状态
docker ps | grep node1

# 查看日志
docker logs -f node1-worker

# 验证Ray集群
docker exec node1-worker ray status
```

---

### 多节点部署

#### 节点1（头节点）部署

**1. 配置节点1**

```bash
# 在节点1服务器上
cd /path/to/secretflow_test
cp config/node1.env .env.production
vim .env.production
```

确保配置：
```bash
NODE_ID=node1
NODE_IP=192.168.1.10
RAY_NODE_TYPE=head
RAY_HEAD_ADDRESS=192.168.1.10:61379
```

**2. 启动节点1**

```bash
bash scripts/deploy.sh
```

**3. 验证节点1**

```bash
docker exec node1-worker ray status
# 应该看到1个节点
```

#### 节点2（工作节点）部署

**1. 配置节点2**

```bash
# 在节点2服务器上
cd /path/to/secretflow_test
cp config/node2.env .env.production
vim .env.production
```

确保配置：
```bash
NODE_ID=node2
NODE_IP=192.168.1.11
RAY_NODE_TYPE=worker
RAY_HEAD_ADDRESS=192.168.1.10:61379  # 指向节点1
SF_PORT_RANGE_START=19100            # 不同的端口范围
SF_PORT_RANGE_END=19109
```

**2. 启动节点2**

```bash
bash scripts/deploy.sh
```

**3. 验证集群**

```bash
# 在任意节点执行
docker exec node1-worker ray status
# 应该看到2个节点
```

---

## 🔧 配置说明

### 环境变量详解

#### 节点基础配置

```bash
NODE_ID=node1              # 节点唯一标识符
NODE_IP=192.168.1.10       # 宿主机真实IP
APP_ENV=production         # 运行环境
```

#### Redis配置

```bash
REDIS_HOST=127.0.0.1       # host模式下使用localhost
REDIS_PORT=60379           # Redis端口
REDIS_DB=0                 # 数据库编号
REDIS_PASSWORD=            # 密码（可选）
```

#### Ray集群配置

```bash
RAY_NODE_TYPE=head                    # head或worker
RAY_HEAD_ADDRESS=192.168.1.10:61379   # 头节点地址
RAY_NODE_IP=192.168.1.10              # 当前节点IP
RAY_PORT=61379                        # Ray GCS端口
RAY_NUM_CPUS=0                        # CPU数量（0=全部）
RAY_OBJECT_STORE_MEMORY=2000000000    # 对象存储内存
```

#### SecretFlow端口配置

```bash
SF_PORT_RANGE_START=19000   # SecretFlow起始端口
SF_PORT_RANGE_END=19009     # SecretFlow结束端口
SPU_PORT_RANGE_START=19500  # SPU起始端口
SPU_PORT_RANGE_END=19509    # SPU结束端口
HEU_PORT_RANGE_START=19800  # HEU起始端口
HEU_PORT_RANGE_END=19809    # HEU结束端口
```

#### Celery Worker配置

```bash
WORKER_CONCURRENCY=2                # 并发数
WORKER_HOSTNAME=node1@127.0.0.1     # Worker主机名
CELERY_LOG_LEVEL=INFO               # 日志级别
WORKER_QUEUES=secretflow_queue      # 任务队列
WORKER_POOL=prefork                 # 进程池类型
```

---

## 🔍 验证部署

### 检查容器状态

```bash
# 查看容器
docker ps | grep node1

# 应该看到两个容器：
# - node1-redis
# - node1-worker
```

### 检查日志

```bash
# Worker日志
docker logs node1-worker

# 应该看到：
# ✅ Ray启动成功
# ✅ Celery Worker已就绪
```

### 验证Ray集群

```bash
# 查看Ray状态
docker exec node1-worker ray status

# 查看节点列表
docker exec node1-worker ray list nodes

# 查看资源
docker exec node1-worker ray list resources
```

### 验证Redis连接

```bash
# 进入容器
docker exec -it node1-worker bash

# 测试Redis连接
python3 -c "
import redis
r = redis.from_url('redis://127.0.0.1:60379/0')
print(r.ping())
"
```

### 测试任务执行

```bash
# 发送测试任务
docker exec node1-worker python3 -c "
from src.celery_app import celery_app
result = celery_app.send_task('tasks.secretflow.hello.ping_task')
print(f'Task ID: {result.id}')
"
```

---

## 🛠️ 运维操作

### 查看日志

```bash
# 实时日志
docker logs -f node1-worker

# 最近100行
docker logs node1-worker --tail 100

# 带时间戳
docker logs node1-worker --timestamps
```

### 重启服务

```bash
# 重启Worker
docker compose -f docker/docker-compose.production.yml \
    --env-file .env.production restart worker

# 重启所有服务
docker compose -f docker/docker-compose.production.yml \
    --env-file .env.production restart
```

### 停止服务

```bash
docker compose -f docker/docker-compose.production.yml \
    --env-file .env.production down
```

### 更新配置

```bash
# 1. 修改配置文件
vim .env.production

# 2. 重新部署
bash scripts/deploy.sh
```

### 进入容器调试

```bash
# 进入Worker容器
docker exec -it node1-worker bash

# 查看进程
ps aux | grep -E "ray|python"

# 查看端口
netstat -tuln | grep LISTEN
```

---

## 🔥 防火墙配置

### CentOS/RHEL

```bash
# 允许Ray通信
firewall-cmd --permanent --add-port=61379/tcp

# 允许SecretFlow通信
firewall-cmd --permanent --add-port=19000-19009/tcp
firewall-cmd --permanent --add-port=19500-19509/tcp
firewall-cmd --permanent --add-port=19800-19809/tcp

# 重载防火墙
firewall-cmd --reload
```

### Ubuntu

```bash
# 允许Ray通信
ufw allow 61379/tcp

# 允许SecretFlow通信
ufw allow 19000:19009/tcp
ufw allow 19500:19509/tcp
ufw allow 19800:19809/tcp

# 重载防火墙
ufw reload
```

---

## ⚠️ 注意事项

### 1. 端口管理

- 确保宿主机端口未被占用
- 不同节点使用不同的SecretFlow端口范围
- 使用`netstat -tuln`检查端口占用

### 2. 网络连通性

- 节点间需要能够直接通信
- 检查防火墙规则
- 使用`ping`和`telnet`测试连通性

### 3. 资源限制

- 确保有足够的内存和CPU
- 监控资源使用情况
- 根据需要调整`RAY_OBJECT_STORE_MEMORY`

### 4. 安全建议

- 生产环境设置Redis密码
- 使用TLS加密节点间通信
- 限制Ray Dashboard访问
- 定期更新依赖包

### 5. 数据持久化

- Redis数据持久化到volume
- Worker数据和日志持久化
- 定期备份重要数据

---

## 📊 性能优化

### Worker并发配置

```bash
# CPU密集型任务
WORKER_CONCURRENCY=<CPU核心数>

# IO密集型任务
WORKER_CONCURRENCY=<CPU核心数 * 2>
```

### Ray内存配置

```bash
# 根据可用内存调整
RAY_OBJECT_STORE_MEMORY=<可用内存的50-70%>
```

### Redis内存配置

```yaml
# docker-compose.production.yml
command: >
  redis-server
  --port ${REDIS_PORT}
  --maxmemory 2gb  # 根据需要调整
```

---

## 🔄 升级流程

### 1. 备份数据

```bash
# 备份Redis数据
docker exec node1-redis redis-cli -p 60379 SAVE

# 备份配置文件
cp .env.production .env.production.backup
```

### 2. 更新代码

```bash
git pull origin main
```

### 3. 重新部署

```bash
bash scripts/deploy.sh
```

### 4. 验证升级

```bash
docker logs node1-worker --tail 50
docker exec node1-worker ray status
```

---

## 📞 故障排查

详见 [troubleshooting.md](troubleshooting.md)

---

## 📚 相关文档

- [设计方案](production_deployment_design_host_network.md)
- [失败尝试总结](summary/failed_attempts.md)
- [故障排查指南](troubleshooting.md)

---

**文档版本**：v2.0  
**最后更新**：2026年1月6日
