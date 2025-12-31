## 生产模式[​](https://www.secretflow.org.cn/zh-CN/docs/secretflow/v1.14.0b0/getting_started/deployment#production)

SecretFlow提供了多控制器模式用于生产以提升安全性。（如果您想了解更多，欢迎阅读[隐语编程思想](https://www.secretflow.org.cn/zh-CN/docs/secretflow/v1.14.0b0/developer/design/programming_in_secretflow)）

用于生产的SecretFlow由多个ray集群组成，每个参与方拥有各自的ray集群。 **与此同时，每一个参与方都要同时执行代码，才能完成任务的协作** 。生产模式的架构如下图所示。

![隐语-数据可信流通技术社区](https://registry.npmmirror.com/@secretflow/x-secretflow/0.1.0-g52ccf50-b20251103065841986562/files/dist/assets/FABWPM63.png)

下列步骤将演示如何部署生产模式的SecretFlow。

### 创建跨机构的SecretFlow集群。[​](https://www.secretflow.org.cn/zh-CN/docs/secretflow/v1.14.0b0/getting_started/deployment#setup-a-secretflow-cluster-crossing-silo)

下面的例子展示了如何构建一个由alice和bob组成的生产集群。

---

**注意**

请牢记alice和bob需要同时运行代码。

---

#### 在alice节点上启动SecretFlow[​](https://www.secretflow.org.cn/zh-CN/docs/secretflow/v1.14.0b0/getting_started/deployment#start-secretflow-on-the-node-of-alice)

alice首先启动ray集群。注意这里的命令是启动Ray的主节点。

```bash
ray start --head --node-ip-address="ip" --port="port" --include-dashboard=False --disable-usage-stats
```

屏幕输出中显示"Ray runtime started."，则说明Ray的主节点启动成功。至此alice的Ray集群已经创建完成。

`alice`使用集群配置初始化SecretFlow，并且运行代码。

---

**提示**

1. 请使用主节点的 `node-ip-address` 和 `port` 填充 `sf.init` 的 `address` 参数。
2. `alice` 的 `address` 请填写可以被bob访通的地址，并且选择一个 **未被占用的端口** ，注意不要和Ray和SPU的端口冲突。
3. `bob` 的 `address` 请填写可以被alice访通的地址，并且选择一个 **未被占用的端口** ，注意不要和Ray和SPU的端口冲突。
4. 注意 `self_party` 为 `alice` 。
5. 请注意sf.init不需要提供 `parties` 参数，而是需要提供 `cluster_config` 来描述两个机构之间的通信地址和端口。
6. 为了确保alice和bob的端口能够被对方访问同时系统的防火墙不被关闭，您应该把alice和bob的IP地址加入到对方的IP白名单
7. telnet 命令通常用于测试端口的可访问性。

---

```python
cluster_config ={
    'parties': {
        'alice': {
            # replace with alice's real address.
            'address': 'ip:port of alice',
            'listen_addr': '0.0.0.0:port'
        },
        'bob': {
            # replace with bob's real address.
            'address': 'ip:port of bob',
            'listen_addr': '0.0.0.0:port'
        },
    },
    'self_party': 'alice'
}

sf.init(address='alice ray head node address', cluster_config=cluster_config)

# your code to run.
```

#### 在bob节点上启动SecretFlow。[​](https://www.secretflow.org.cn/zh-CN/docs/secretflow/v1.14.0b0/getting_started/deployment#start-secretflow-on-the-node-of-bob)

bob首先启动ray集群

```
ray start --head --node-ip-address="ip" --port="port" --include-dashboard=False --disable-usage-stats
```

屏幕输出中显示"Ray runtime started."，则说明Ray的主节点启动成功。至此bob的Ray集群已经创建完成。

bob使用和alice类似的集群配置初始化SecretFlow，除了 `self_party` 字段稍有不同。然后运行代码。

---

**提示**

1. 使用主节点的 `node-ip-address` 和 `port`来填充 `sf.init` 的 `address` 参数。注意，这里填写的是bob的头节点地址，请不要填写成alice的。
2. `alice` 的 `address` 请填写可以被bob访通的地址，并且选择一个 **未被占用的端口** ，注意不要和Ray和SPU的端口冲突。
3. `bob` 的 `address` 请填写可以被alice访通的地址，并且选择一个 **未被占用的端口** ，注意不要和Ray和SPU的端口冲突。
4. 注意`self_party` 为 `bob`。
5. 请注意sf.init不需要提供 `parties` 参数，而是需要提供 `cluster_config` 来描述两个机构之间的通信地址和端口。
6. 为了确保alice和bob的端口能够被对方访问同时系统的防火墙不被关闭，您应该把alice和bob的IP地址加入到对方的IP白名单
7. telnet 命令通常用于测试端口的可访问性。

---

```
cluster_config ={
    'parties': {
        'alice': {
            # replace with alice's real address.
            'address': 'ip:port of alice',
            'listen_addr': '0.0.0.0:port'
        },
        'bob': {
            # replace with bob's real address.
            'address': 'ip:port of bob',
            'listen_addr': '0.0.0.0:port'
        },
    },
    'self_party': 'bob'
}

sf.init(address='bob ray head node address', cluster_config=cluster_config)

# your code to run.
```

### 如何构建SPU[​](https://www.secretflow.org.cn/zh-CN/docs/secretflow/v1.14.0b0/getting_started/deployment#how-to-setup-spu-for-production)

除了SPU的创建需要多个参会方同时执行外，创建SPU的方式与模拟模式一样，请阅读前文了解更多细节。

为了避免启动时差带来的比如连接超时等问题，您可能需要设置SPU的`link_desc`参数来调整连接相关参数，具体参见 [SPU](https://www.secretflow.org.cn/zh-CN/docs/secretflow/v1.14.0b0/source/secretflow.device.device#secretflow.device.device.spu.SPU.__init__)

### 生产环境建议[​](https://www.secretflow.org.cn/zh-CN/docs/secretflow/v1.14.0b0/getting_started/deployment#suggestions-for-production)

1. 启动tls验证。
    
    SecretFlow的跨机构grpc通信可以配置TLS以提升安全性。
    
    alice的配置示例。
    
    ```
    tls_config = {
        "ca_cert": "ca root cert of other parties (e.g. bob)",
        "cert": "server cert of alice in pem",
        "key": "server key of alice in pem",
    }
    
    sf.init(address='ip:port',
            cluster_config=cluster_config,
            tls_config=tls_config
    )
    ```
    
    bob的配置示例。
    
    ```
    tls_config = {
        "ca_cert": "ca root cert of other parties (e.g. alice)",
        "cert": "server cert of bob in pem",
        "key": "server key of bob in pem",
    }
    
    sf.init(address='ip:port',
            cluster_config=cluster_config,
            tls_config=tls_config
    )
    ```
    
2. 序列化/反序列化增强。
    
    SecretFlow uses `pickle` in serialization/deserialization which is vulnerable. You can set `cross_silo_serializing_allowed_list` when init SecretFlow to specify an allowlist to restrict serializable objects. An example could be （**You should not use this demo directly. Configure it to your actual needs.**）
    
    ```
    allowed_list =  {
        "numpy.core.numeric": ["*"],
        "numpy": ["dtype"],
    }
    
    sf.init(address='ip:port',
            cluster_config=cluster_config,
            cross_silo_serializing_allowed_list=allowed_list
    )
    ```