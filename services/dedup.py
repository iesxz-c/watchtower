import hashlib

def generate_fingerprint(*args) -> str:
    """Generate a SHA-256 fingerprint from string arguments."""
    hasher = hashlib.sha256()
    for arg in args:
        if arg is not None:
            hasher.update(str(arg).encode('utf-8'))
    return hasher.hexdigest()
