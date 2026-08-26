import os
import requests
from dotenv import load_dotenv

# 加载.env文件
load_dotenv(override=True)

def send_bark_notification(title, content):
    """
    使用iOS Bark发送通知
    :param title: 通知标题
    :param content: 通知内容
    :return: 发送结果
    """
    try:
        # 从环境变量获取Bark配置
        bark_server = os.getenv('BARK_SERVER', 'https://api.day.app')
        bark_key = os.getenv('BARK_KEY')
        
        if not bark_key:
            print("❌ Bark密钥未配置，请在.env文件中设置BARK_KEY")
            return False
        
        # 构建Bark API URL
        url = f"{bark_server}/{bark_key}/{title}/{content}"
        
        # 发送通知请求
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        print(f"✅ Bark通知发送成功: {title}")
        print(f"   响应内容: {response.text}")
        return True
    except Exception as e:
        print(f"❌ Bark通知发送失败: {e}")
        return False

if __name__ == "__main__":
    print("📱 测试Bark通知功能")
    print(f"🔑 当前Bark密钥: {os.getenv('BARK_KEY')}")
    
    # 发送测试通知
    title = "测试通知"
    content = "这是一条来自Python脚本的测试通知"
    
    send_bark_notification(title, content)