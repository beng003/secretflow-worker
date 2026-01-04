import secretflow as sf
from secretflow.ml.linear.ss_sgd.model import SSGLr
print("SSGLr found at secretflow.ml.linear.ss_sgd.model.SSGLr")
try:
    from secretflow.preprocessing import StandardScaler
    print("StandardScaler found at secretflow.preprocessing")
except ImportError:
    print("StandardScaler not found at secretflow.preprocessing")

try:
    from secretflow.data.split import train_test_split
    print("train_test_split found at secretflow.data.split")
except ImportError:
    print("train_test_split not found at secretflow.data.split")
