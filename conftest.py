"""
Pytest配置文件

配置pytest测试环境，确保src目录在Python路径中
"""

import sys
from pathlib import Path

# 将src目录添加到Python路径
src_path = Path(__file__).parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))
