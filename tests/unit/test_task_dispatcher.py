"""
TaskDispatcher单元测试

测试任务分发器的所有核心功能，包括任务注册、分发、异常处理等。
"""

import pytest
from unittest.mock import Mock, patch
from secretflow_task.task_dispatcher import TaskDispatcher


class TestTaskDispatcher:
    """TaskDispatcher测试类"""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """每个测试前后清理注册表"""
        # 保存原始注册表
        original_registry = TaskDispatcher.TASK_REGISTRY.copy()

        # 清空注册表
        TaskDispatcher.clear_registry()

        yield

        # 恢复原始注册表
        TaskDispatcher.TASK_REGISTRY = original_registry

    def test_register_task_success(self):
        """测试任务注册成功"""

        @TaskDispatcher.register_task("test_task")
        def test_func(devices, task_config):
            return {"status": "success"}

        # 验证任务已注册
        assert "test_task" in TaskDispatcher.TASK_REGISTRY
        assert TaskDispatcher.TASK_REGISTRY["test_task"] == test_func

    def test_register_task_duplicate_raises_error(self):
        """测试重复注册任务抛出异常"""

        @TaskDispatcher.register_task("duplicate_task")
        def first_func(devices, task_config):
            return {}

        # 尝试重复注册应该抛出ValueError
        with pytest.raises(ValueError) as exc_info:

            @TaskDispatcher.register_task("duplicate_task")
            def second_func(devices, task_config):
                return {}

        assert "已注册" in str(exc_info.value)
        assert "duplicate_task" in str(exc_info.value)

    def test_register_multiple_tasks(self):
        """测试注册多个任务"""

        @TaskDispatcher.register_task("task1")
        def func1(devices, task_config):
            return {"task": "1"}

        @TaskDispatcher.register_task("task2")
        def func2(devices, task_config):
            return {"task": "2"}

        @TaskDispatcher.register_task("task3")
        def func3(devices, task_config):
            return {"task": "3"}

        # 验证所有任务都已注册
        assert len(TaskDispatcher.TASK_REGISTRY) == 3
        assert "task1" in TaskDispatcher.TASK_REGISTRY
        assert "task2" in TaskDispatcher.TASK_REGISTRY
        assert "task3" in TaskDispatcher.TASK_REGISTRY

    def test_dispatch_success(self):
        """测试任务分发成功"""

        @TaskDispatcher.register_task("test_dispatch")
        def test_func(devices, task_config):
            return {
                "status": "success",
                "devices_count": len(devices),
                "config": task_config,
            }

        # 准备测试数据
        devices = {"alice": Mock(), "bob": Mock()}
        task_config = {"param1": "value1", "param2": "value2"}

        # 执行分发
        result = TaskDispatcher.dispatch("test_dispatch", devices, task_config)

        # 验证结果
        assert result["status"] == "success"
        assert result["devices_count"] == 2
        assert result["config"] == task_config

    def test_dispatch_nonexistent_task_raises_error(self):
        """测试分发不存在的任务抛出异常"""
        devices = {"alice": Mock()}
        task_config = {}

        # 分发不存在的任务应该抛出ValueError
        with pytest.raises(ValueError) as exc_info:
            TaskDispatcher.dispatch("nonexistent_task", devices, task_config)

        assert "不支持的任务类型" in str(exc_info.value)
        assert "nonexistent_task" in str(exc_info.value)

    def test_dispatch_with_task_exception(self):
        """测试任务执行过程中抛出异常"""

        @TaskDispatcher.register_task("failing_task")
        def failing_func(devices, task_config):
            raise RuntimeError("任务执行失败")

        devices = {"alice": Mock()}
        task_config = {}

        # 任务执行异常应该被传播
        with pytest.raises(RuntimeError) as exc_info:
            TaskDispatcher.dispatch("failing_task", devices, task_config)

        assert "任务执行失败" in str(exc_info.value)

    def test_list_supported_tasks_empty(self):
        """测试空注册表返回空列表"""
        tasks = TaskDispatcher.list_supported_tasks()
        assert tasks == []

    def test_list_supported_tasks_sorted(self):
        """测试任务列表按字母顺序排序"""

        @TaskDispatcher.register_task("zebra")
        def func1(devices, task_config):
            return {}

        @TaskDispatcher.register_task("apple")
        def func2(devices, task_config):
            return {}

        @TaskDispatcher.register_task("banana")
        def func3(devices, task_config):
            return {}

        tasks = TaskDispatcher.list_supported_tasks()
        assert tasks == ["apple", "banana", "zebra"]

    def test_get_task_info_success(self):
        """测试获取任务信息成功"""

        @TaskDispatcher.register_task("info_task")
        def test_func(devices, task_config):
            """这是一个测试函数"""
            return {}

        info = TaskDispatcher.get_task_info("info_task")

        assert info["task_type"] == "info_task"
        assert info["function_name"] == "test_func"
        assert "测试函数" in info["doc"]

    def test_get_task_info_nonexistent_raises_error(self):
        """测试获取不存在任务的信息抛出异常"""
        with pytest.raises(ValueError) as exc_info:
            TaskDispatcher.get_task_info("nonexistent")

        assert "不存在" in str(exc_info.value)

    def test_clear_registry(self):
        """测试清空注册表"""

        @TaskDispatcher.register_task("task1")
        def func1(devices, task_config):
            return {}

        @TaskDispatcher.register_task("task2")
        def func2(devices, task_config):
            return {}

        assert len(TaskDispatcher.TASK_REGISTRY) == 2

        TaskDispatcher.clear_registry()

        assert len(TaskDispatcher.TASK_REGISTRY) == 0

    def test_decorator_returns_original_function(self):
        """测试装饰器返回原始函数"""

        def original_func(devices, task_config):
            return {"original": True}

        decorated_func = TaskDispatcher.register_task("decorator_test")(original_func)

        # 装饰器应该返回原始函数
        assert decorated_func == original_func
        assert decorated_func({}, {})["original"] is True

    def test_dispatch_with_empty_devices(self):
        """测试使用空设备字典分发任务"""

        @TaskDispatcher.register_task("empty_devices_task")
        def test_func(devices, task_config):
            return {"devices_count": len(devices)}

        result = TaskDispatcher.dispatch("empty_devices_task", {}, {})
        assert result["devices_count"] == 0

    def test_dispatch_with_complex_config(self):
        """测试使用复杂配置分发任务"""

        @TaskDispatcher.register_task("complex_config_task")
        def test_func(devices, task_config):
            return task_config

        complex_config = {
            "nested": {"level1": {"level2": "value"}},
            "list": [1, 2, 3],
            "boolean": True,
            "number": 42,
        }

        result = TaskDispatcher.dispatch("complex_config_task", {}, complex_config)
        assert result == complex_config

    def test_task_function_receives_correct_parameters(self):
        """测试任务函数接收正确的参数"""
        received_devices = None
        received_config = None

        @TaskDispatcher.register_task("param_test")
        def test_func(devices, task_config):
            nonlocal received_devices, received_config
            received_devices = devices
            received_config = task_config
            return {}

        test_devices = {"alice": "device1", "bob": "device2"}
        test_config = {"key": "value"}

        TaskDispatcher.dispatch("param_test", test_devices, test_config)

        assert received_devices == test_devices
        assert received_config == test_config

    @patch("secretflow_task.task_dispatcher.logger")
    def test_dispatch_logs_execution(self, mock_logger):
        """测试分发过程记录日志"""

        @TaskDispatcher.register_task("log_test")
        def test_func(devices, task_config):
            return {}

        TaskDispatcher.dispatch("log_test", {}, {})

        # 验证日志被调用
        assert mock_logger.info.called

    @patch("secretflow_task.task_dispatcher.logger")
    def test_dispatch_logs_error_on_failure(self, mock_logger):
        """测试任务失败时记录错误日志"""

        @TaskDispatcher.register_task("error_log_test")
        def test_func(devices, task_config):
            raise ValueError("测试错误")

        with pytest.raises(ValueError):
            TaskDispatcher.dispatch("error_log_test", {}, {})

        # 验证错误日志被调用
        assert mock_logger.error.called

    def test_register_task_with_special_characters(self):
        """测试使用特殊字符的任务类型"""

        @TaskDispatcher.register_task("task-with-dash")
        def func1(devices, task_config):
            return {}

        @TaskDispatcher.register_task("task_with_underscore")
        def func2(devices, task_config):
            return {}

        @TaskDispatcher.register_task("task.with.dot")
        def func3(devices, task_config):
            return {}

        assert "task-with-dash" in TaskDispatcher.TASK_REGISTRY
        assert "task_with_underscore" in TaskDispatcher.TASK_REGISTRY
        assert "task.with.dot" in TaskDispatcher.TASK_REGISTRY

    def test_dispatch_preserves_return_value_type(self):
        """测试分发保持返回值类型"""

        @TaskDispatcher.register_task("return_dict")
        def func_dict(devices, task_config):
            return {"type": "dict"}

        @TaskDispatcher.register_task("return_list")
        def func_list(devices, task_config):
            return ["type", "list"]

        @TaskDispatcher.register_task("return_string")
        def func_string(devices, task_config):
            return "string"

        result_dict = TaskDispatcher.dispatch("return_dict", {}, {})
        result_list = TaskDispatcher.dispatch("return_list", {}, {})
        result_string = TaskDispatcher.dispatch("return_string", {}, {})

        assert isinstance(result_dict, dict)
        assert isinstance(result_list, list)
        assert isinstance(result_string, str)


class TestTaskDispatcherEdgeCases:
    """TaskDispatcher边界条件测试"""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """每个测试前后清理注册表"""
        original_registry = TaskDispatcher.TASK_REGISTRY.copy()
        TaskDispatcher.clear_registry()
        yield
        TaskDispatcher.TASK_REGISTRY = original_registry

    def test_register_task_with_empty_string(self):
        """测试使用空字符串注册任务"""

        @TaskDispatcher.register_task("")
        def test_func(devices, task_config):
            return {}

        # 空字符串也是有效的任务类型
        assert "" in TaskDispatcher.TASK_REGISTRY

    def test_dispatch_with_none_values(self):
        """测试使用None值分发任务"""

        @TaskDispatcher.register_task("none_test")
        def test_func(devices, task_config):
            return {"devices": devices, "config": task_config}

        # 虽然不推荐，但应该能处理None值
        result = TaskDispatcher.dispatch("none_test", None, None)
        assert result["devices"] is None
        assert result["config"] is None

    def test_concurrent_registration(self):
        """测试并发注册场景（模拟）"""
        # 注册多个任务，模拟并发场景
        for i in range(100):

            @TaskDispatcher.register_task(f"concurrent_task_{i}")
            def test_func(devices, task_config):
                return {"id": i}

        # 验证所有任务都已注册
        assert len(TaskDispatcher.TASK_REGISTRY) == 100

        # 验证所有任务都可以被分发
        for i in range(100):
            result = TaskDispatcher.dispatch(f"concurrent_task_{i}", {}, {})
            assert "id" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
