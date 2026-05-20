"""
Lightweight ML utilities - Drop-in replacements for sklearn.
Same API, but using numpy/scipy only (~5KB vs 100MB).

Features:
- StandardScaler
- PCA (Principal Component Analysis)
- Simple pattern detection
"""

import numpy as np
from typing import Tuple, Optional, List

# =========================
# SCALER
# =========================

class StandardScaler:
    """
    Drop-in replacement for sklearn.preprocessing.StandardScaler.
    Standardizes features by removing mean and scaling to unit variance.
    """
    
    def __init__(self):
        self.mean_ = None
        self.scale_ = None
        self.var_ = None
        self.n_features_in_ = None
    
    def fit(self, X: np.ndarray) -> 'StandardScaler':
        """Compute mean and standard deviation."""
        X = np.asarray(X)
        
        if len(X.shape) == 1:
            X = X.reshape(-1, 1)
        
        self.n_features_in_ = X.shape[1]
        self.mean_ = np.mean(X, axis=0)
        self.var_ = np.var(X, axis=0)
        self.scale_ = np.sqrt(self.var_)
        self.scale_[self.scale_ == 0] = 1.0  # Avoid division by zero
        
        return self
    
    def transform(self, X: np.ndarray) -> np.ndarray:
        """Scale features."""
        X = np.asarray(X)
        
        if len(X.shape) == 1:
            X = X.reshape(-1, 1)
        
        if self.mean_ is None:
            raise ValueError("Scaler has not been fitted yet.")
        
        return (X - self.mean_) / self.scale_
    
    def fit_transform(self, X: np.ndarray) -> np.ndarray:
        """Fit and transform."""
        return self.fit(X).transform(X)
    
    def inverse_transform(self, X: np.ndarray) -> np.ndarray:
        """Inverse transform (denormalize)."""
        X = np.asarray(X)
        return X * self.scale_ + self.mean_


# =========================
# PCA
# =========================

class PCA:
    """
    Drop-in replacement for sklearn.decomposition.PCA.
    Principal Component Analysis using numpy SVD.
    """
    
    def __init__(self, n_components: int = 2):
        self.n_components = n_components
        self.components_ = None
        self.explained_variance_ = None
        self.explained_variance_ratio_ = None
        self.mean_ = None
        self.n_samples_ = None
        self.n_features_in_ = None
    
    def fit(self, X: np.ndarray) -> 'PCA':
        """Learn principal components."""
        X = np.asarray(X)
        
        if len(X.shape) == 1:
            X = X.reshape(-1, 1)
        
        self.n_samples_, self.n_features_in_ = X.shape
        
        # Center data
        self.mean_ = np.mean(X, axis=0)
        X_centered = X - self.mean_
        
        # SVD
        U, S, Vt = np.linalg.svd(X_centered, full_matrices=False)
        
        # Get components
        self.components_ = Vt[:self.n_components]
        
        # Explained variance
        self.explained_variance_ = (S ** 2) / (self.n_samples_ - 1)
        self.explained_variance_ratio_ = self.explained_variance_ / np.sum(self.explained_variance_)
        
        return self
    
    def transform(self, X: np.ndarray) -> np.ndarray:
        """Project data onto principal components."""
        X = np.asarray(X)
        
        if len(X.shape) == 1:
            X = X.reshape(-1, 1)
        
        if self.components_ is None:
            raise ValueError("PCA has not been fitted yet.")
        
        X_centered = X - self.mean_
        return np.dot(X_centered, self.components_.T)
    
    def fit_transform(self, X: np.ndarray) -> np.ndarray:
        """Fit and transform."""
        return self.fit(X).transform(X)
    
    def inverse_transform(self, X_transformed: np.ndarray) -> np.ndarray:
        """Inverse transform (reconstruct)."""
        X_transformed = np.asarray(X_transformed)
        return np.dot(X_transformed, self.components_) + self.mean_


# =========================
# CLUSTERING (K-Means)
# =========================

class KMeans:
    """Simple K-Means clustering (lightweight alternative to sklearn)."""
    
    def __init__(self, n_clusters: int = 3, max_iter: int = 100, random_state: Optional[int] = None):
        self.n_clusters = n_clusters
        self.max_iter = max_iter
        self.random_state = random_state
        self.cluster_centers_ = None
        self.labels_ = None
        self.inertia_ = None
    
    def fit(self, X: np.ndarray) -> 'KMeans':
        """Fit K-Means."""
        X = np.asarray(X)
        n_samples, n_features = X.shape
        
        # Initialize centers randomly
        if self.random_state is not None:
            np.random.seed(self.random_state)
        
        indices = np.random.choice(n_samples, self.n_clusters, replace=False)
        self.cluster_centers_ = X[indices].copy()
        
        # Iterate
        for _ in range(self.max_iter):
            # Assign clusters
            distances = np.sqrt(((X - self.cluster_centers_[:, np.newaxis]) ** 2).sum(axis=2))
            labels = np.argmin(distances, axis=0)
            
            # Update centers
            new_centers = np.array([X[labels == k].mean(axis=0) 
                                   for k in range(self.n_clusters)])
            
            # Check convergence
            if np.allclose(self.cluster_centers_, new_centers):
                break
            
            self.cluster_centers_ = new_centers
        
        self.labels_ = labels
        
        # Compute inertia
        distances = np.sqrt(((X - self.cluster_centers_[labels]) ** 2).sum(axis=1))
        self.inertia_ = (distances ** 2).sum()
        
        return self
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict cluster labels."""
        X = np.asarray(X)
        distances = np.sqrt(((X - self.cluster_centers_[:, np.newaxis]) ** 2).sum(axis=2))
        return np.argmin(distances, axis=0)
    
    def fit_predict(self, X: np.ndarray) -> np.ndarray:
        """Fit and predict."""
        return self.fit(X).labels_


# =========================
# UTILITIES
# =========================

def cosine_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine distance between vectors."""
    a = np.asarray(a).flatten()
    b = np.asarray(b).flatten()
    
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    
    if norm_a == 0 or norm_b == 0:
        return 1.0
    
    return 1.0 - np.dot(a, b) / (norm_a * norm_b)


def euclidean_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Compute Euclidean distance between vectors."""
    return float(np.linalg.norm(np.asarray(a) - np.asarray(b)))


def normalize(X: np.ndarray, axis: int = 1) -> np.ndarray:
    """Normalize array."""
    X = np.asarray(X)
    norm = np.linalg.norm(X, axis=axis, keepdims=True)
    norm[norm == 0] = 1.0
    return X / norm
