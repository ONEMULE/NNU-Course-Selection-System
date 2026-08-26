import os
import requests
from dotenv import load_dotenv

# 加载.env文件中的环境变量
load_dotenv()

# 从环境变量获取敏感信息
school_url = os.getenv('SCHOOL_URL')
username = os.getenv('USERNAME')
password = os.getenv('PASSWORD')

# 检查是否所有必要的环境变量都已设置
if not all([school_url, username, password]):
    print("错误: 请在.env文件中设置完整的SCHOOL_URL、USERNAME和PASSWORD信息")
    exit(1)

# 创建会话对象
session = requests.Session()

try:
    # 发送GET请求获取登录页面，用于获取可能需要的csrf token等信息
    response = session.get(school_url)
    response.raise_for_status()  # 检查请求是否成功
    
    # 这里需要根据实际网站的登录表单结构调整
    # 通常需要查看网页源码找到表单的action、method以及输入字段的name属性
    # 以下是一个通用的登录请求示例，需要根据实际情况修改
    login_data = {
        'username': username,  # 替换为实际表单中的用户名字段名
        'password': password,  # 替换为实际表单中的密码字段名
        # 可能需要添加其他字段，如csrfmiddlewaretoken、__VIEWSTATE等
        # 这些字段通常可以从登录页面的HTML中提取
    }
    
    # 发送POST请求进行登录
    login_response = session.post(school_url, data=login_data)
    login_response.raise_for_status()
    
    # 验证登录是否成功（根据实际情况调整验证逻辑）
    # 例如检查响应内容是否包含登录后的特定字符串或URL是否重定向
    if "登录成功" in login_response.text or "欢迎" in login_response.text:
        print("登录成功！")
    else:
        print("登录失败，请检查账号密码或网络连接")
        
    # 登录成功后，可以使用session对象访问其他需要登录的页面
    # 例如: session.get("https://example.com/dashboard")
    
except requests.exceptions.RequestException as e:
    print(f"网络请求错误: {e}")
except Exception as e:
    print(f"登录过程中发生错误: {e}")
