import sys
import os

try:
    import secretflow as sf
    print(f"SecretFlow version: {sf.__version__}")
    
    # Try importing SSGLr
    try:
        from secretflow.ml.linear.ss_sgd.model import SSGLr
        print("SSGLr found at: secretflow.ml.linear.ss_sgd.model")
    except ImportError:
        print("SSGLr NOT found at secretflow.ml.linear.ss_sgd.model")
        try:
            from secretflow.ml.linear import SSGLr
            print("SSGLr found at: secretflow.ml.linear")
        except ImportError:
            print("SSGLr NOT found at secretflow.ml.linear")

    # Try importing preprocessing
    try:
        from secretflow.preprocessing import StandardScaler
        print("StandardScaler found at: secretflow.preprocessing")
    except ImportError:
        print("StandardScaler NOT found at secretflow.preprocessing")
        
except ImportError as e:
    print(f"ImportError: {e}")
