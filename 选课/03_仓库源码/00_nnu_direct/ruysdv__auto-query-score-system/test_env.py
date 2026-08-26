import os
from dotenv import load_dotenv

# 加载.env文件，使用override=True覆盖系统环境变量
load_dotenv(override=True)

# 读取环境变量
school_url = os.getenv('SCHOOL_URL')
username = os.getenv('SCHOOL_USERNAME')
password = os.getenv('SCHOOL_PASSWORD')

# 打印读取到的变量，验证是否正确
def print_env_var(name, value):
    print(f"{name} = '{value}'")
    print(f"长度: {len(value)}")
    print()

print("从.env文件读取的环境变量:")
print("=" * 50)
print_env_var('SCHOOL_URL', school_url)
print_env_var('SCHOOL_USERNAME', username)
print_env_var('SCHOOL_PASSWORD', password)

# 验证密码是否包含特殊字符
if password and '#' in password:
    print("✅ 密码中成功包含了特殊字符#")
else:
    print("❌ 密码中未能正确包含特殊字符#")
