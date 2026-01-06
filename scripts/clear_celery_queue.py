import redis
import sys
import os

# 添加src目录到路径以便导入配置
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))

from config.settings import settings

def clear_celery_tasks():
    print("🧹 开始清理 Celery 任务队列...")
    try:
        r = redis.from_url(settings.redis_url)
        
        # 清理 Celery 相关的所有键
        keys = r.keys("celery*") + r.keys("unacked*") + r.keys("_kombu*") + r.keys("secretflow_queue") + r.keys("default") + r.keys("web_queue")
        
        if keys:
            print(f"发现 {len(keys)} 个相关键，正在删除...")
            r.delete(*keys)
            print("✅ 队列清理完成")
        else:
            print("✨ 队列已经是空的")
            
    except Exception as e:
        print(f"❌ 清理失败: {e}")

if __name__ == "__main__":
    clear_celery_tasks()
