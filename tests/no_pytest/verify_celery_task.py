import sys
import os
import time

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))

from secretflow_task.hello import ping_task, echo_task

def verify_celery_tasks():
    print("🚀 开始验证Celery任务...")
    
    # 1. 验证 Ping 任务
    print("\n[1/2] 发送 Ping 任务...")
    try:
        # 直接调用 delay (apply_async)
        result = ping_task.delay()
        print(f"  任务已提交, ID: {result.id}")
        
        # 等待结果
        try:
            output = result.get(timeout=10)
            print(f"  ✅ Ping 任务成功! 结果: {output}")
        except Exception as e:
            print(f"  ❌ Ping 任务超时或失败: {e}")
            return False
            
    except Exception as e:
        print(f"  ❌ 提交 Ping 任务失败: {e}")
        return False

    # 2. 验证 Echo 任务 (参数传递)
    print("\n[2/2] 发送 Echo 任务...")
    test_data = {"key": "value", "timestamp": time.time()}
    try:
        result = echo_task.delay(data=test_data)
        print(f"  任务已提交, ID: {result.id}")
        
        try:
            output = result.get(timeout=10)
            if output.get('echoed_data') == test_data:
                print("  ✅ Echo 任务成功! 数据匹配。")
            else:
                print(f"  ❌ Echo 任务数据不匹配: {output}")
        except Exception as e:
            print(f"  ❌ Echo 任务超时或失败: {e}")
            return False
            
    except Exception as e:
        print(f"  ❌ 提交 Echo 任务失败: {e}")
        return False
        
    print("\n✅ Celery 任务系统验证通过!")
    return True

if __name__ == "__main__":
    if verify_celery_tasks():
        sys.exit(0)
    else:
        sys.exit(1)
