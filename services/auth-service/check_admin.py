from security import verify_password
hash = "$2b$12$kUJEWCIyqgLZ9biN95LXROy8DAMkbju85zGLqedQikWXLgeKomLkK"
result = verify_password("Admin@REVO2025", hash)
print("Password valid:", result)
if not result:
    from security import hash_password
    new_hash = hash_password("Admin@REVO2025")
    print("New hash:", new_hash)
