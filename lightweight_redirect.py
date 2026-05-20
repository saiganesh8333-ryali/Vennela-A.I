"""
Import redirection layer - Automatically replaces heavy imports with lightweight versions.

This module patches the import system to redirect:
- sentence_transformers -> lightweight_embeddings
- transformers -> lightweight_nlp
- sklearn -> lightweight_ml

When a module tries to import from these heavy libraries, it automatically
uses the lightweight versions instead.

Usage:
1. Import this module at the very start of your application
2. All subsequent imports will automatically redirect to lightweight versions

Example:
    import sys
    import lightweight_redirect
    
    # Now these imports use lightweight versions:
    from sentence_transformers import SentenceTransformer
    from transformers import pipeline
    from sklearn.preprocessing import StandardScaler
"""

import sys
import importlib.abc
import importlib.machinery
from typing import Optional, List

# =========================
# IMPORT HOOKS
# =========================

class LightweightImportRedirector(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """Redirects heavy library imports to lightweight versions."""
    
    REDIRECT_MAP = {
        'sentence_transformers': 'lightweight_embeddings',
        'transformers': 'lightweight_nlp',
        'sklearn': 'lightweight_ml',
        'sklearn.preprocessing': 'lightweight_ml',
        'sklearn.decomposition': 'lightweight_ml',
        'torch': None,  # Filter out torch (use numpy instead)
    }
    
    def find_spec(self, fullname, path, target=None):
        """Find module spec and redirect if needed."""
        if fullname in self.REDIRECT_MAP:
            redirect_to = self.REDIRECT_MAP[fullname]
            
            if redirect_to is None:
                # torch -> silently replace with numpy stub
                return importlib.machinery.ModuleSpec(fullname, self)
            else:
                # Redirect to lightweight module
                try:
                    real_module = importlib.import_module(redirect_to)
                    spec = importlib.util.spec_from_loader(fullname, self)
                    return spec
                except ImportError:
                    pass
        
        return None
    
    def load_module(self, fullname):
        """Load module (handle torch stub case)."""
        if fullname == 'torch':
            # Return numpy stub
            return self._create_torch_stub()
        
        redirect_to = self.REDIRECT_MAP.get(fullname)
        if redirect_to:
            return importlib.import_module(redirect_to)
        
        return None
    
    def exec_module(self, module):
        """Execute module."""
        pass
    
    @staticmethod
    def _create_torch_stub():
        """Create a stub module for torch that redirects to numpy."""
        import types
        import numpy as np
        
        torch_stub = types.ModuleType('torch')
        
        # Expose numpy functions under torch namespace
        torch_stub.Tensor = np.ndarray
        torch_stub.tensor = np.array
        torch_stub.zeros = np.zeros
        torch_stub.ones = np.ones
        torch_stub.randn = np.random.randn
        torch_stub.nn = types.ModuleType('nn')
        torch_stub.cuda = types.ModuleType('cuda')
        torch_stub.cuda.is_available = lambda: False
        
        return torch_stub


# =========================
# ACTIVATION
# =========================

def install_redirector():
    """Install the import redirector."""
    redirector = LightweightImportRedirector()
    
    # Install at the start of sys.meta_path
    if not any(isinstance(finder, LightweightImportRedirector) for finder in sys.meta_path):
        sys.meta_path.insert(0, redirector)
        print("[Lightweight Mode] Import redirector installed - heavy libraries redirected to lightweight versions")


def uninstall_redirector():
    """Uninstall the import redirector."""
    sys.meta_path[:] = [
        finder for finder in sys.meta_path
        if not isinstance(finder, LightweightImportRedirector)
    ]


# =========================
# MANUAL PATCHES (Fallback)
# =========================

def patch_imports():
    """
    Manually patch imports in sys.modules for modules already loaded.
    Call this if install_redirector() is called too late.
    """
    import lightweight_embeddings
    import lightweight_nlp
    import lightweight_ml
    
    # Add to sys.modules
    sys.modules['sentence_transformers'] = lightweight_embeddings
    sys.modules['transformers'] = lightweight_nlp
    sys.modules['sklearn'] = lightweight_ml
    sys.modules['sklearn.preprocessing'] = lightweight_ml
    sys.modules['sklearn.decomposition'] = lightweight_ml
    sys.modules['torch'] = _create_torch_stub()
    
    print("[Lightweight Mode] Manual patches applied to sys.modules")


def _create_torch_stub():
    """Create torch stub module."""
    import types
    import numpy as np
    
    torch_stub = types.ModuleType('torch')
    torch_stub.Tensor = np.ndarray
    torch_stub.tensor = np.array
    torch_stub.zeros = np.zeros
    torch_stub.ones = np.ones
    torch_stub.randn = np.random.randn
    
    nn_stub = types.ModuleType('nn')
    nn_stub.Module = object
    nn_stub.Linear = lambda *args: None
    torch_stub.nn = nn_stub
    
    cuda_stub = types.ModuleType('cuda')
    cuda_stub.is_available = lambda: False
    torch_stub.cuda = cuda_stub
    
    return torch_stub


# =========================
# AUTO-SETUP
# =========================

# Install redirector when this module is imported
install_redirector()

__all__ = ['install_redirector', 'uninstall_redirector', 'patch_imports']
