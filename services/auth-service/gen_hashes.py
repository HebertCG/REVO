from passlib.context import CryptContext
ctx = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__truncate_error=False)
print("Admin hash:", ctx.hash("Admin@1234"))
print("Demo hash:", ctx.hash("Demo@1234"))
print("Hebertjose89 hash:", ctx.hash("Hebertjose89"))
