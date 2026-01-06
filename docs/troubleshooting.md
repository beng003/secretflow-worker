# SecretFlow生产环境故障排查指南

## 📋 文档信息

- **版本**：v2.0
- **网络模式**：Host Network
- **更新时间**：2026年1月6日

---

## 🔍 常见问题

### 1. 容器无法启动

#### 问题表现
```bash
docker ps | grep node1
# 容器不存在或状态为Restarting
```

#### 排查步骤

**1.1 查看容器日志**
```bash
docker logs node1-worker --tail 100
```

**1.2 检查配置文件**
```bash
# 确认配置文件存在
ls -la .env.production

# 检查配置语法
cat .env.production | grep -v "^#" | grep -v "^$"
```

**1.3 检查端口占用**
```bash
# 检查Redis端口
netstat -tuln | grep 60379

# 检查Ray端口
netstat -tuln | grep 61379

# 检查SecretFlow端口范围
netstat -tuln | grep -E "19[0-9]{3}"
```

**1.4 检查Docker网络**
```bash
# Host模式不需要创建网络，但要确保宿主机网络正常
ip addr show
```

#### 解决方案

**端口被占用**：
```bash
# 查找占用进程
lsof -i :60379

# 停止占用进程或修改配置使用其他端口
vim .env.production
```

**配置错误**：
```bash
# 重新从模板创建
cp config/production.env.template .env.production
vim .env.production
```

---

### 2. Ray集群无法启动

#### 问题表现
```bash
docker logs node1-worker | grep Ray
# 看到Ray启动失败的错误
```

#### 排查步骤

**2.1 检查Ray日志**
```bash
docker logs node1-worker 2>&1 | grep -A 10 "Ray"
```

**2.2 检查Ray进程**
```bash
docker exec node1-worker ps aux | grep ray
```

**2.3 检查Ray端口**
```bash
docker exec node1-worker netstat -tuln | grep 61379
```

#### 常见错误

**错误1：端口已被占用**
```
OSError: [Errno 98] Address already in use
```

解决方案：
```bash
# 检查宿主机端口
netstat -tuln | grep 61379

# 修改RAY_PORT配置
vim .env.production
# RAY_PORT=61380  # 使用其他端口
```

**错误2：无法连接到头节点**
```
ConnectionError: Failed to connect to Ray cluster at 192.168.1.10:61379
```

解决方案：
```bash
# 检查头节点是否运行
ssh user@192.168.1.10 "docker ps | grep worker"

# 检查网络连通性
ping 192.168.1.10
telnet 192.168.1.10 61379

# 检查防火墙
firewall-cmd --list-ports
```

**错误3：Python兼容性问题**
```
ValueError: <object object at 0x...> is not a valid Sentinel
```

解决方案：
- 这是旧方案的问题，新方案使用命令行启动Ray，已避免此问题
- 如果仍出现，检查是否使用了正确的entrypoint.sh

---

### 3. Worker无法连接Redis

#### 问题表现
```bash
docker logs node1-worker | grep Redis
# 看到Redis连接失败
```

#### 排查步骤

**3.1 检查Redis容器**
```bash
docker ps | grep redis
docker logs node1-redis
```

**3.2 测试Redis连接**
```bash
# 从宿主机测试
redis-cli -h 127.0.0.1 -p 60379 ping

# 从容器内测试
docker exec node1-worker redis-cli -h 127.0.0.1 -p 60379 ping
```

**3.3 检查Redis配置**
```bash
docker exec node1-redis redis-cli -p 60379 CONFIG GET port
docker exec node1-redis redis-cli -p 60379 CONFIG GET bind
```

#### 解决方案

**Redis未启动**：
```bash
# 重启Redis
docker compose -f docker/docker-compose.production.yml \
    --env-file .env.production restart redis
```

**端口配置错误**：
```bash
# 检查配置一致性
grep REDIS_PORT .env.production
# 确保Worker和Redis使用相同端口
```

**网络问题**：
```bash
# Host模式下应该使用127.0.0.1
# 检查REDIS_HOST配置
grep REDIS_HOST .env.production
# 应该是: REDIS_HOST=127.0.0.1
```

---

### 4. 多节点Ray集群连接失败

#### 问题表现
```bash
docker exec node1-worker ray status
# 只看到1个节点，应该有2个或更多
```

#### 排查步骤

**4.1 检查节点配置**
```bash
# 在工作节点上检查配置
grep RAY_HEAD_ADDRESS .env.production
# 应该指向头节点IP和端口
```

**4.2 检查网络连通性**
```bash
# 从工作节点ping头节点
ping 192.168.1.10

# 测试Ray端口连通性
telnet 192.168.1.10 61379
```

**4.3 检查防火墙**
```bash
# 在头节点上检查防火墙
firewall-cmd --list-ports | grep 61379

# 如果端口未开放
firewall-cmd --permanent --add-port=61379/tcp
firewall-cmd --reload
```

**4.4 检查Ray日志**
```bash
# 在工作节点查看Ray连接日志
docker logs node2-worker 2>&1 | grep -i "connect"
```

#### 解决方案

**防火墙阻止**：
```bash
# 在头节点开放Ray端口
firewall-cmd --permanent --add-port=61379/tcp
firewall-cmd --reload
```

**配置错误**：
```bash
# 确保工作节点配置正确
vim .env.production
# RAY_NODE_TYPE=worker
# RAY_HEAD_ADDRESS=<头节点IP>:61379
```

**时序问题**：
```bash
# 确保头节点先启动
# 然后等待30秒再启动工作节点
sleep 30
bash scripts/deploy.sh
```

---

### 5. 任务执行失败

#### 问题表现
```bash
# 任务一直pending或失败
```

#### 排查步骤

**5.1 检查Worker状态**
```bash
docker logs node1-worker | grep -i "ready"
```

**5.2 检查Celery队列**
```bash
docker exec node1-worker celery -A src.celery_app inspect active
docker exec node1-worker celery -A src.celery_app inspect reserved
```

**5.3 检查任务日志**
```bash
docker logs node1-worker | grep -i "task"
```

**5.4 检查资源使用**
```bash
docker stats node1-worker
```

#### 解决方案

**Worker未就绪**：
```bash
# 重启Worker
docker compose -f docker/docker-compose.production.yml \
    --env-file .env.production restart worker
```

**资源不足**：
```bash
# 增加内存限制
vim docker/docker-compose.production.yml
# 添加资源限制配置

# 或调整Worker并发数
vim .env.production
# WORKER_CONCURRENCY=1  # 降低并发
```

**任务超时**：
```bash
# 增加超时时间
vim .env.production
# WORKER_TASK_SOFT_TIME_LIMIT=7200
# WORKER_TASK_TIME_LIMIT=7500
```

---

### 6. 端口冲突

#### 问题表现
```bash
docker logs node1-worker
# Address already in use
```

#### 排查步骤

**6.1 扫描端口占用**
```bash
# 扫描所有相关端口
nmap -p 60379,61379,19000-19009 localhost
```

**6.2 查找占用进程**
```bash
lsof -i :60379
lsof -i :61379
```

#### 解决方案

**停止冲突进程**：
```bash
# 找到PID后
kill -9 <PID>
```

**修改端口配置**：
```bash
vim .env.production
# 使用其他端口
# REDIS_PORT=60380
# RAY_PORT=61380
```

---

### 7. 性能问题

#### 问题表现
- 任务执行缓慢
- CPU/内存使用率高
- 响应延迟

#### 排查步骤

**7.1 监控资源使用**
```bash
# 实时监控
docker stats

# 查看容器资源
docker exec node1-worker top
```

**7.2 检查Ray资源**
```bash
docker exec node1-worker ray status
docker exec node1-worker ray list resources
```

**7.3 检查网络延迟**
```bash
# 测试节点间延迟
ping -c 10 192.168.1.11
```

#### 优化方案

**增加Worker并发**：
```bash
vim .env.production
# WORKER_CONCURRENCY=4  # 根据CPU核心数调整
```

**增加Ray内存**：
```bash
vim .env.production
# RAY_OBJECT_STORE_MEMORY=4000000000  # 增加到4GB
```

**优化Redis**：
```yaml
# docker-compose.production.yml
command: >
  redis-server
  --port ${REDIS_PORT}
  --maxmemory 4gb
  --maxmemory-policy allkeys-lru
```

---

## 🛠️ 调试工具

### 进入容器调试

```bash
# 进入Worker容器
docker exec -it node1-worker bash

# 查看进程
ps aux | grep -E "ray|python|celery"

# 查看端口
netstat -tuln | grep LISTEN

# 查看环境变量
env | grep -E "RAY|REDIS|NODE"

# 测试Python导入
python3 -c "import ray; import secretflow; print('OK')"
```

### 查看Ray详细信息

```bash
# Ray状态
docker exec node1-worker ray status --verbose

# Ray节点列表
docker exec node1-worker ray list nodes

# Ray资源
docker exec node1-worker ray list resources

# Ray任务
docker exec node1-worker ray list tasks

# Ray日志
docker exec node1-worker cat /tmp/ray/session_latest/logs/raylet.out
```

### 查看Celery信息

```bash
# Celery状态
docker exec node1-worker celery -A src.celery_app status

# 活动任务
docker exec node1-worker celery -A src.celery_app inspect active

# 注册任务
docker exec node1-worker celery -A src.celery_app inspect registered

# 统计信息
docker exec node1-worker celery -A src.celery_app inspect stats
```

### 网络诊断

```bash
# 检查端口监听
netstat -tuln | grep -E "60379|61379|19000"

# 检查连接状态
netstat -anp | grep ESTABLISHED

# 测试端口连通性
telnet 192.168.1.10 61379

# 路由追踪
traceroute 192.168.1.10
```

---

## 📊 日志分析

### 关键日志位置

```bash
# Worker日志
docker logs node1-worker

# Redis日志
docker logs node1-redis

# Ray日志（容器内）
/tmp/ray/session_latest/logs/

# Celery日志（容器内）
/app/logs/
```

### 日志过滤技巧

```bash
# 只看错误
docker logs node1-worker 2>&1 | grep -i error

# 只看Ray相关
docker logs node1-worker 2>&1 | grep -i ray

# 只看任务执行
docker logs node1-worker 2>&1 | grep -i task

# 带时间戳
docker logs node1-worker --timestamps

# 实时跟踪
docker logs node1-worker -f --tail 50
```

---

## 🔄 恢复流程

### 完全重新部署

```bash
# 1. 停止所有服务
docker compose -f docker/docker-compose.production.yml \
    --env-file .env.production down -v

# 2. 清理旧镜像
docker rmi secretflow-worker:latest

# 3. 清理数据（可选，会丢失数据）
docker volume prune

# 4. 重新部署
bash scripts/deploy.sh
```

### 保留数据重启

```bash
# 1. 停止服务（不删除volume）
docker compose -f docker/docker-compose.production.yml \
    --env-file .env.production down

# 2. 重新启动
docker compose -f docker/docker-compose.production.yml \
    --env-file .env.production up -d
```

---

## 📞 获取帮助

### 收集诊断信息

```bash
#!/bin/bash
# 诊断信息收集脚本

echo "=== 系统信息 ===" > diagnosis.txt
uname -a >> diagnosis.txt
docker --version >> diagnosis.txt
docker compose version >> diagnosis.txt

echo -e "\n=== 容器状态 ===" >> diagnosis.txt
docker ps -a >> diagnosis.txt

echo -e "\n=== 配置文件 ===" >> diagnosis.txt
cat .env.production | grep -v PASSWORD >> diagnosis.txt

echo -e "\n=== Worker日志 ===" >> diagnosis.txt
docker logs node1-worker --tail 200 >> diagnosis.txt 2>&1

echo -e "\n=== Redis日志 ===" >> diagnosis.txt
docker logs node1-redis --tail 50 >> diagnosis.txt 2>&1

echo -e "\n=== 端口占用 ===" >> diagnosis.txt
netstat -tuln | grep -E "60379|61379|19000" >> diagnosis.txt

echo -e "\n=== Ray状态 ===" >> diagnosis.txt
docker exec node1-worker ray status >> diagnosis.txt 2>&1

echo "诊断信息已保存到 diagnosis.txt"
```

### 联系支持

提供以下信息：
1. 诊断信息文件（diagnosis.txt）
2. 问题描述和复现步骤
3. 环境信息（操作系统、Docker版本等）
4. 错误日志和截图

---

## 📚 相关文档

- [部署指南](deployment_guide.md)
- [设计方案](production_deployment_design_host_network.md)
- [失败尝试总结](summary/failed_attempts.md)

---

**文档版本**：v2.0  
**最后更新**：2026年1月6日
