import sys
sys.path.insert(0, ".")
from security import verify_password, hash_password

# Test the stored hash
stored = "$2b$12$YPyOpRGPG1531jPzu1W7eeTmX3vrsvtuRRuqBLKFv4W4EwidQ3JZO"
result = verify_password("Admin@REVO2025", stored)
print("Verify stored hash:", result)

if not result:
    # Generate fresh hash
    new = hash_password("Admin@REVO2025")
    print("New hash:", new)
    print("Self-verify:", verify_password("Admin@REVO2025", new))
