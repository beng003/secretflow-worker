# SecretFlow PSI 隐私计算演示环境

本项目提供了一个完整的 SecretFlow PSI (Private Set Intersection) 隐私计算演示环境，使用 Docker Compose 启动两个容器模拟 Alice 和 Bob 两个参与方，演示隐私集合交集计算。

## 🎯 项目概述

### PSI 隐私集合交集
PSI 允许两方在不泄露各自数据的情况下计算数据集的交集。在此演示中：
- **Alice**: 拥有用户基础信息（用户ID、姓名、年龄等）
- **Bob**: 拥有用户购买记录（用户ID、产品、金额等）
- **目标**: 找出共同用户，用于联邦学习或联合分析

### 架构设计
```
┌─────────────────┐         ┌─────────────────┐
│   Alice 容器     │ ◄─────► │    Bob 容器      │
│  (172.20.0.10)  │         │  (172.20.0.20)  │
│                 │         │                 │
│  • Ray Head     │         │  • Ray Worker   │
│  • SPU Node     │         │  • SPU Node     │
│  • PSI 发起方   │         │  • PSI 参与方   │
└─────────────────┘         └─────────────────┘
```

## 🚀 快速启动

### 前置要求
- Docker >= 20.10
- Docker Compose >= 2.0
- 可用内存 >= 4GB

### 启动步骤

1. **启动演示环境**
```bash
cd docker
./scripts/start_psi.sh
```

2. **监控日志**
```bash
# 查看 Alice 节点日志
docker-compose logs -f alice

# 查看 Bob 节点日志  
docker-compose logs -f bob
```

3. **查看计算结果**
```bash
# Alice 的结果文件
docker-compose exec alice cat /data/alice/alice_output.csv
docker-compose exec alice cat /data/alice/psi_stats.csv

# Bob 的结果文件
docker-compose exec bob cat /data/bob/bob_stats.csv
```

## 📊 数据说明

### Alice 的数据集
- **文件**: `/data/alice/alice_input.csv`
- **记录数**: 1,000 条用户记录
- **字段**: `user_id`, `name`, `age`, `city`, `income`
- **用户范围**: `user_0001` 到 `user_1000`

### Bob 的数据集  
- **文件**: `/data/bob/bob_input.csv`
- **记录数**: 1,000 条购买记录
- **字段**: `user_id`, `product`, `purchase_amount`, `purchase_date`, `category`
- **用户范围**: `user_0500` 到 `user_1500`

### 期望交集
- **重叠用户**: `user_0500` 到 `user_1000` (约500个用户)
- **交集大小**: 500条记录

## 🔧 技术细节

### SecretFlow 配置
- **协议**: KKRT_PSI_2PC (两方 PSI)
- **通信**: SPU 安全多方计算单元
- **网络**: Ray 分布式计算框架

### 容器配置
- **基础镜像**: `secretflow/secretflow-anolis8:latest`
- **网络**: 自定义 bridge 网络 (172.20.0.0/24)
- **端口映射**: 
  - Alice: 8000 (HTTP), 9394 (Ray), 12945 (SPU)
  - Bob: 8001 (HTTP), 12946 (SPU)

### 目录结构
```
docker/
├── docker-compose.yml      # 容器编排配置
├── alice/
│   └── Dockerfile         # Alice 容器配置
├── bob/  
│   └── Dockerfile         # Bob 容器配置
├── scripts/
│   ├── alice_psi.py       # Alice PSI 计算脚本
│   ├── bob_psi.py         # Bob PSI 计算脚本
│   └── start_psi.sh       # 启动脚本
├── data/
│   ├── alice/             # Alice 数据目录
│   └── bob/               # Bob 数据目录
└── README.md              # 本文档
```

## 📈 性能与监控

### 计算指标
- **计算时间**: 通常 30-60 秒
- **内存使用**: 每个容器 ~1-2GB
- **网络通信**: SPU 节点间加密通信

### 监控工具
```bash
# 查看容器资源使用
docker stats sf_alice sf_bob

# 检查网络连通性
docker-compose exec alice ping bob
docker-compose exec bob ping alice

# 查看 Ray 集群状态
docker-compose exec alice ray status
```

## 🛡️ 安全特性

### 隐私保护
- **数据不出域**: 原始数据不离开各自容器
- **安全多方计算**: 使用密码学协议保护计算过程
- **零知识**: 除了交集结果，不泄露任何其他信息

### 加密通信
- **TLS 加密**: SPU 节点间通信加密
- **身份认证**: 参与方身份验证
- **防窃听**: 网络传输层安全

## 🔍 故障排除

### 常见问题

**1. 容器启动失败**
```bash
# 检查端口占用
netstat -tulpn | grep -E ":(8000|8001|9394|12945|12946)"

# 清理之前的容器
docker-compose down --volumes --remove-orphans
```

**2. PSI 计算超时**
```bash
# 检查容器间网络连通性
docker-compose exec alice ping -c 3 bob
docker-compose exec bob ping -c 3 alice

# 查看详细日志
docker-compose logs --details alice
docker-compose logs --details bob
```

**3. Ray 集群连接失败**
```bash
# 重启 Ray 集群
docker-compose restart alice bob

# 检查 Ray 状态
docker-compose exec alice ray status
```

### 日志位置
- Alice 日志: `/data/alice/alice.log`
- Bob 日志: `/data/bob/bob.log`
- Docker 日志: `docker-compose logs`

## 🎓 学习资源

### SecretFlow 文档
- [官方文档](https://www.secretflow.org.cn/docs/secretflow/)
- [PSI 教程](https://www.secretflow.org.cn/docs/secretflow/latest/en/tutorial/PSI.html)
- [API 参考](https://www.secretflow.org.cn/docs/secretflow/latest/en/source/secretflow.html)

### 隐私计算概念
- [隐私集合交集 (PSI)](https://en.wikipedia.org/wiki/Private_set_intersection)
- [安全多方计算 (MPC)](https://en.wikipedia.org/wiki/Secure_multi-party_computation)
- [联邦学习](https://en.wikipedia.org/wiki/Federated_learning)

## 📄 许可证

本项目采用与 SecretFlow 相同的开源许可证。详见 [LICENSE](../LICENSE) 文件。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request 来改进这个演示环境！

---

**注意**: 本演示环境仅用于学习和测试目的，生产环境需要额外的安全配置和性能优化。
