import os
import re
import json
import requests
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

# 加载.env文件中的环境变量，使用override=True覆盖系统环境变量
load_dotenv(override=True)

# 从环境变量获取敏感信息
school_url = os.getenv('SCHOOL_URL')
username = os.getenv('SCHOOL_USERNAME')
password = os.getenv('SCHOOL_PASSWORD')

# 检查是否所有必要的环境变量都已设置
if not all([school_url, username, password]):
    print("错误: 请在.env文件中设置完整的SCHOOL_URL、SCHOOL_USERNAME和SCHOOL_PASSWORD信息")
    exit(1)

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
        return True
    except Exception as e:
        print(f"❌ Bark通知发送失败: {e}")
        return False

def main():
    # 配置Chrome驱动程序为无头模式（不显示浏览器窗口）
    chrome_options = webdriver.ChromeOptions()
    # 启用无头模式
    chrome_options.add_argument('--headless')
    # 禁用GPU加速（无头模式下推荐）
    chrome_options.add_argument('--disable-gpu')
    # 设置浏览器窗口大小
    chrome_options.add_argument('--window-size=1920,1080')
    # 提高无头模式的稳定性
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    # 禁用浏览器通知
    chrome_options.add_argument('--disable-notifications')
    # 设置用户代理（可选，但有时需要）
    chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36')
    
    # 初始化WebDriver，使用webdriver-manager自动管理驱动
    driver = webdriver.Chrome(
        service=ChromeService(ChromeDriverManager().install()),
        options=chrome_options
    )
    
    try:
        # 导航到登录页面
        driver.get(school_url)
        # 无头模式下不需要最大化窗口
        
        # 等待页面加载完成（根据实际情况调整等待时间）
        time.sleep(2)
        
        print("当前页面标题:", driver.title)
        print("当前页面URL:", driver.current_url)
        
        # 检查是否有统一身份认证登录选项
        try:
            # 尝试找到统一身份认证登录的选项（使用多种选择器）
            unified_login_button = None
            
            # 尝试不同的选择器
            try:
                # 通过文本内容查找
                unified_login_button = driver.find_element(By.XPATH, '//a[contains(text(), "统一身份认证") or contains(text(), "统一认证") or contains(text(), "SSO")]')
            except:
                try:
                    # 通过class查找
                    unified_login_button = driver.find_element(By.CLASS_NAME, 'unified-login')
                except:
                    try:
                        # 通过id查找
                        unified_login_button = driver.find_element(By.ID, 'unified-login')
                    except:
                        try:
                            # 通过其他可能的文本
                            unified_login_button = driver.find_element(By.XPATH, '//button[contains(text(), "统一身份认证") or contains(text(), "统一认证")]')
                        except:
                            pass
            
            if unified_login_button:
                print("✅ 找到统一身份认证登录选项")
                unified_login_button.click()
                print("✅ 已点击统一身份认证登录选项")
                time.sleep(2)  # 等待页面跳转
                print("跳转后页面标题:", driver.title)
                print("跳转后页面URL:", driver.current_url)
            else:
                print("ℹ️  未找到统一身份认证登录选项，尝试直接登录")
                
        except Exception as e:
            print(f"ℹ️  查找统一身份认证登录选项时发生错误: {e}")
            print("ℹ️  将尝试直接登录")
        
        # 检查当前页面是否已经是登录页面（无论是原始还是SSO页面）
        current_url = driver.current_url
        
        # 查找用户名和密码输入框
        username_input = None
        password_input = None
        login_button = None
        
        # 添加调试信息：获取页面的部分HTML内容
        try:
            page_html = driver.page_source[:2000]  # 获取前2000个字符
            print(f"\n页面部分HTML内容: {page_html}")
        except Exception as e:
            print(f"获取页面HTML时出错: {e}")
        
        # 针对华南师范大学SSO页面的特定选择器
        try:
            # 尝试使用更多可能的选择器
            print("\n尝试查找用户名输入框...")
            
            # 优化：只使用已验证有效的方法
            try:
                username_input = driver.find_element(By.XPATH, "//input[@type='text'][1]")
                print("✅ 通过第一个text输入框找到用户名输入框")
            except Exception as e:
                print(f"❌ 查找用户名输入框失败: {e}")
            
            print("\n尝试查找密码输入框...")
            
            # 优化：只使用已验证有效的方法
            try:
                password_input = driver.find_element(By.ID, "password")
                print("✅ 通过ID 'password'找到密码输入框")
            except Exception as e:
                print(f"❌ 查找密码输入框失败: {e}")
            
            print("\n尝试查找登录按钮...")
            
            # 优化：只使用已验证有效的方法
            try:
                login_button = driver.find_element(By.XPATH, "//button[contains(text(), '登录') or contains(text(), 'Login') or contains(text(), 'Submit')]")
                print("✅ 通过按钮文本找到登录按钮")
            except Exception as e:
                print(f"❌ 查找登录按钮失败: {e}")
                    
        except Exception as e:
            print(f"查找登录表单元素时发生错误: {e}")
        
        if username_input and password_input and login_button:
            print("\n✅ 成功找到所有登录表单元素！")
            
            # 输入账号密码
            username_input.send_keys(username)
            password_input.send_keys(password)
            print("✅ 已输入账号密码")
            
            # 点击登录按钮
            login_button.click()
            print("✅ 已点击登录按钮")
            
            # 等待登录过程完成并验证是否成功
            time.sleep(3)  # 等待页面加载
        else:
            print(f"\n❌ 无法找到所有登录表单元素:")
            print(f"   用户名输入框: {'找到' if username_input else '未找到'}")
            print(f"   密码输入框: {'找到' if password_input else '未找到'}")
            print(f"   登录按钮: {'找到' if login_button else '未找到'}")
            raise Exception("无法找到登录表单元素")
        
        print("登录后页面标题:", driver.title)
        print("登录后页面URL:", driver.current_url)
        
        # 处理登录后的流程
        login_attempts = 1
        max_attempts = 3  # 最多尝试3次登录
        
        while login_attempts < max_attempts:
            current_url = driver.current_url
            current_title = driver.title
            
            print(f"\n第{login_attempts}次循环检查:")
            print(f"当前URL: {current_url}")
            print(f"当前标题: {current_title}")
            
            # 检测是否跳转到登录确认页面
            if "openapi/auth.html" in current_url:
                login_attempts += 1
                print(f"⚠️  检测到登录确认页面，正在处理...")
                
                try:
                    # 在登录确认页面查找确认按钮（只使用已验证有效的方法）
                    confirm_button = None
                    
                    # 优化：直接查找"确定登录"文本的可交互元素
                    try:
                        confirm_button = driver.find_element(By.XPATH, "//button[contains(text(), '确定登录') or contains(text(), '确认')] | //a[contains(text(), '确定登录') or contains(text(), '确认')] | //div[@role='button' and contains(text(), '确定登录') or contains(text(), '确认')]")
                        print("✅ 直接找到'确定登录'按钮")
                    except Exception as e:
                        print(f"❌ 查找确认按钮失败: {e}")
                    
                    if confirm_button:
                        try:
                            # 获取并打印基本信息
                            elem_text = confirm_button.text.strip() or "无文本"
                            print(f"✅ 找到登录确认按钮: '{elem_text}'")
                            
                            # 立即使用JavaScript点击，减少等待时间
                            driver.execute_script("arguments[0].scrollIntoView(true); arguments[0].click();", confirm_button)
                            print("✅ 已快速点击登录确认按钮")
                            time.sleep(2)  # 减少等待时间
                            print(f"点击确认后页面标题:", driver.title)
                            print(f"点击确认后页面URL:", driver.current_url)
                            
                        except Exception as e:
                            print(f"❌ 点击确认按钮时发生错误: {e}")
                            
                            # 尝试查找所有可交互元素并显示它们
                            try:
                                interactive_elements = driver.find_elements(By.XPATH, "//button | //a | //input[@type='submit'] | //div[@role='button']")
                                print(f"\n调试信息: 找到 {len(interactive_elements)} 个可交互元素:")
                                for i, elem in enumerate(interactive_elements[:10]):  # 只显示前10个
                                    try:
                                        elem_text = elem.text.strip() or f"{elem.tag_name}元素"
                                        elem_id = elem.get_attribute('id') or '无ID'
                                        elem_class = elem.get_attribute('class') or '无class'
                                        print(f"   {i+1}. {elem.tag_name} - '{elem_text}' - ID: {elem_id} - Class: {elem_class}")
                                    except:
                                        pass
                            except:
                                pass
                    else:
                        print("ℹ️  未找到登录确认按钮，可能页面自动跳转")
                        time.sleep(3)
                        
                except Exception as e:
                    print(f"❌ 处理登录确认页面时发生错误: {e}")
                    break
            
            # 检测是否跳转到统一身份验证登录页面（需要输入账号密码的页面）
            elif "sso.scnu.edu.cn/AccountService/user/login.html" in current_url:
                login_attempts += 1
                print(f"⚠️  检测到统一身份验证登录页面，正在进行第{login_attempts}次登录...")
                
                try:
                    # 尝试找到并填写登录表单
                    username_input = None
                    password_input = None
                    login_button = None
                    
                    # 尝试找到用户名输入框（使用测试中有效的方法）
                    try:
                        username_input = driver.find_element(By.XPATH, "//input[@type='text'][1]")
                    except:
                        pass
                    
                    # 尝试找到密码输入框
                    try:
                        password_input = driver.find_element(By.ID, "password")
                    except:
                        try:
                            password_input = driver.find_element(By.XPATH, "//input[@type='password'][1]")
                        except:
                            pass
                    
                    # 尝试找到登录按钮
                    try:
                        login_button = driver.find_element(By.XPATH, "//button[contains(text(), '登录')]")
                    except:
                        pass
                    
                    if username_input and password_input and login_button:
                        username_input.send_keys(username)
                        password_input.send_keys(password)
                        print("✅ 已在统一身份验证页面输入账号密码")
                        
                        login_button.click()
                        print("✅ 已在统一身份验证页面点击登录按钮")
                        time.sleep(3)
                    else:
                        print("❌ 无法找到统一身份验证页面的登录表单元素")
                        break
                        
                except Exception as e:
                    print(f"❌ 统一身份验证登录过程中发生错误: {e}")
                    break
            
            # 检测是否在原始登录页面需要再次登录
            elif "login_slogin.html" in current_url:
                login_attempts += 1
                print(f"⚠️  检测到原始登录页面，正在进行第{login_attempts}次尝试...")
                
                try:
                    # 尝试在原始登录页面找到登录表单
                    username_input = driver.find_element(By.XPATH, '//input[@placeholder="请输入用户名" or @placeholder="用户名" or @id="username" or @name="username"]')
                    password_input = driver.find_element(By.XPATH, '//input[@placeholder="请输入密码" or @placeholder="密码" or @id="password" or @name="password"]')
                    
                    if username_input and password_input:
                        username_input.send_keys(username)
                        password_input.send_keys(password)
                        print("✅ 已再次输入账号密码")
                        
                        login_button = driver.find_element(By.XPATH, '//button[contains(text(), "登录") or contains(text(), "Login") or @type="submit"]')
                        login_button.click()
                        print("✅ 已再次点击登录按钮")
                        time.sleep(3)
                    else:
                        break
                        
                except Exception:
                    break
            
            # 检测是否已经登录成功（URL不包含登录相关内容）
            elif "login" not in current_url.lower() and "sso" not in current_url.lower():
                print("ℹ️  当前页面不包含登录或SSO相关内容，可能已登录成功")
                break
            
            else:
                # 如果不是以上情况，说明可能需要更多时间加载
                print("ℹ️  当前页面未匹配到已知模式，等待后重试...")
                time.sleep(2)
                login_attempts += 1
        
        # 最终验证登录是否成功
        final_url = driver.current_url
        final_title = driver.title
        
        print(f"\n最终验证结果:")
        print(f"最终URL: {final_url}")
        print(f"最终标题: {final_title}")
        
        # 验证登录是否成功的条件
        if ("/main" in final_url or "/dashboard" in final_url or "/index" in final_url or 
            "欢迎" in final_title or "首页" in final_title or "教学管理" in final_title or
            "login" not in final_url.lower() and "sso" not in final_url.lower()):
            print("✅ 登录成功！")
            
            # 处理底部的"已阅读"按钮
            print("\n开始处理底部'已阅读'按钮...")
            time.sleep(5)  # 等待5秒
            
            try:
                read_button = None
                
                # 优化：只使用已验证有效的方法
                try:
                    # 精确查找可点击的已阅读按钮
                    read_button = driver.find_element(By.XPATH, "//button[contains(text(), '已阅读') or contains(text(), '我已阅读') or contains(text(), '同意')] | //a[contains(text(), '已阅读') or contains(text(), '我已阅读') or contains(text(), '同意')] | //div[@role='button' and (contains(text(), '已阅读') or contains(text(), '我已阅读') or contains(text(), '同意'))] | //input[@type='checkbox' and contains(@id, 'read') or contains(@name, 'read')]")
                    print("✅ 精确找到可点击的'已阅读'按钮")
                except Exception as e:
                    print(f"❌ 查找'已阅读'按钮失败: {e}")
                
                # 如果找到按钮，点击它
                if read_button:
                    try:
                        button_text = read_button.text.strip() or read_button.get_attribute('value') or "无文本"
                        button_tag = read_button.tag_name
                        
                        print(f"\n准备点击: '{button_text}' ({button_tag})")
                        
                        # 确保元素可见并点击
                        driver.execute_script("arguments[0].scrollIntoView(true);", read_button)
                        time.sleep(0.5)
                        
                        # 根据元素类型选择点击方式
                        if read_button.tag_name == 'input' and read_button.get_attribute('type') == 'checkbox':
                            # 对于复选框，先检查是否已选中
                            if not read_button.is_selected():
                                read_button.click()
                                print("✅ 已勾选'已阅读'复选框")
                            else:
                                print("✅ '已阅读'复选框已选中")
                        else:
                            # 对于普通按钮，使用JavaScript点击
                            driver.execute_script("arguments[0].click();", read_button)
                            print("✅ 已点击'已阅读'按钮")
                        
                        # 等待页面跳转
                        time.sleep(3)
                        print(f"点击后页面URL: {driver.current_url}")
                        print(f"点击后页面标题: {driver.title}")
                        
                    except Exception as e:
                        print(f"❌ 点击按钮时发生错误: {e}")
                        
                        # 调试信息：显示所有可见按钮
                        try:
                            all_visible_buttons = driver.find_elements(By.XPATH, "//button[not(contains(@style, 'display:none'))] | //a[not(contains(@style, 'display:none'))] | //div[@role='button' and not(contains(@style, 'display:none'))]")
                            print(f"\n调试: 找到 {len(all_visible_buttons)} 个可见按钮:")
                            for i, btn in enumerate(all_visible_buttons[-10:]):  # 只显示最后10个
                                try:
                                    btn_text = btn.text.strip() or f"{btn.tag_name}元素"
                                    print(f"   {i+1}. {btn_text}")
                                except:
                                    continue
                        except:
                            pass
                else:
                    print("ℹ️  未找到'已阅读'按钮，可能不需要点击或页面结构不同")
                    
            except Exception as e:
                print(f"❌ 处理'已阅读'按钮时发生错误: {e}")
        else:
            print("❌ 登录失败，请检查账号密码或网页结构是否发生变化")
            print("提示：请根据实际网页结构修改脚本中的元素选择器")
            print(f"总共尝试次数: {login_attempts}次")
        
        # 登录成功后，获取成绩信息
        current_courses = []
        if ("/main" in final_url or "/dashboard" in final_url or "/index" in final_url or 
            "欢迎" in final_title or "首页" in final_title or "教学管理" in final_title or
            "login" not in final_url.lower() and "sso" not in final_url.lower()):
            try:
                print("\n开始获取成绩信息...")
                
                # 简化：直接从页面中提取所有课程名称
                print("1. 提取课程名称...")
                
                # 获取页面所有可见文本
                page_text = driver.page_source
                
                # 使用正则表达式匹配课程信息（只关注课程名称）
                import re
                course_pattern = r'202[4-9]-202[5-9]-\d-(必修|选修|公选|任选|限选)-(.*?)\s*(?=\d+\.?\d*|$)'
                course_matches = re.findall(course_pattern, page_text, re.DOTALL | re.MULTILINE)
                
                # 提取课程名称
                current_courses = []
                if course_matches:
                    for match in course_matches:
                        course_name = match[1].strip()
                        if course_name and len(course_name) > 2:  # 过滤掉无效的课程名称
                            current_courses.append(course_name)
                
                # 如果正则匹配失败，尝试直接查找包含课程信息的元素
                if not current_courses:
                    print("   正则匹配失败，尝试直接查找元素...")
                    course_elements = driver.find_elements(By.XPATH, "//*[contains(text(), '2025-2026') and contains(text(), '课')]")
                    
                    for element in course_elements:
                        try:
                            element_text = element.text.strip()
                            if element_text and '2025-2026' in element_text:
                                # 提取课程名称
                                parts = element_text.split('-')
                                if len(parts) >= 4:
                                    course_name = '-'.join(parts[3:])
                                    # 移除可能的分数部分
                                    if ' ' in course_name:
                                        course_name = course_name.split(' ')[0]
                                    if course_name and len(course_name) > 2:
                                        current_courses.append(course_name)
                        except Exception as e:
                            print(f"   解析元素失败: {e}")
                            continue
                
                # 去重
                current_courses = list(set(current_courses))
                
                if current_courses:
                    print(f"✅ 成功提取 {len(current_courses)} 门课程:")
                    for course in current_courses:
                        print(f"   - {course}")
                        
                    # 数据持久化：保存课程信息并找出新增课程
                    try:
                        # 读取已保存的课程
                        saved_courses = []
                        try:
                            with open('saved_courses.json', 'r', encoding='utf-8') as f:
                                saved_courses = json.load(f)
                        except (FileNotFoundError, json.JSONDecodeError):
                            print("   首次运行，创建新的课程记录文件")
                            saved_courses = []
                        
                        # 找出新增课程
                        new_courses = list(set(current_courses) - set(saved_courses))
                        
                        if new_courses:
                            print(f"\n✅ 发现 {len(new_courses)} 门新增课程:")
                            for course in new_courses:
                                print(f"   - {course}")
                        else:
                            print("\nℹ️  没有发现新增课程")
                        
                        # 保存更新后的课程列表
                        with open('saved_courses.json', 'w', encoding='utf-8') as f:
                            json.dump(current_courses, f, ensure_ascii=False, indent=2)
                        print(f"✅ 课程信息已保存到 saved_courses.json")
                        
                        # 如果有新增课程，立即发送Bark通知
                        if new_courses and len(new_courses) > 0:
                            title = "🎉 新成绩通知"
                            content = "\n".join([f"• {course}" for course in new_courses])
                            send_bark_notification(title, content)
                        
                        # 传递新增课程信息到后续处理
                        return new_courses
                    except Exception as e:
                        print(f"❌ 数据持久化失败: {e}")
                else:
                    print("❌ 未提取到课程信息")
            except Exception as e:
                print(f"❌ 获取成绩信息时发生错误: {e}")
                import traceback
                traceback.print_exc()
        
        # 保持浏览器打开一段时间以便观察结果
        time.sleep(5)
        
    except Exception as e:
        print(f"❌ 登录过程中发生错误: {e}")
        print("\n错误分析与解决建议:")
        print("1. 检查元素选择器是否与实际网页结构匹配")
        print("2. 可以使用浏览器开发者工具(F12)查看网页HTML结构")
        print("3. 在开发者工具中使用'选择元素'功能获取正确的XPath")
        print("4. 调整脚本中的等待时间，确保页面完全加载")
        new_courses = []
        
        # 发送错误通知
        error_title = "⚠️  成绩监控错误"
        error_content = f"登录过程中发生错误：{str(e)}"
        send_bark_notification(error_title, error_content)
    finally:
        # 关闭浏览器
        driver.quit()
    
    return new_courses

def cleanup_records():
    """
    清理记录，避免内存堆积
    每小时清理一次，最多保留最新的30条记录
    """
    try:
        # 检查saved_courses.json文件
        if os.path.exists('saved_courses.json'):
            with open('saved_courses.json', 'r', encoding='utf-8') as f:
                saved_courses = json.load(f)
            
            # 如果记录超过30条，只保留最新的30条
            if len(saved_courses) > 30:
                # 实际应用中应该按时间排序，这里假设列表顺序就是时间顺序
                cleaned_courses = saved_courses[-30:]
                
                with open('saved_courses.json', 'w', encoding='utf-8') as f:
                    json.dump(cleaned_courses, f, ensure_ascii=False, indent=2)
                
                print(f"🧹 清理了 {len(saved_courses) - 30} 条旧记录，保留最新的30条")
                return True
        
        return False
    except Exception as e:
        print(f"❌ 清理记录失败: {e}")
        return False

if __name__ == "__main__":
    print("📊 成绩监控系统已启动")
    print("⏰ 将每1分钟检查一次新成绩")
    print("📱 如有新成绩，将通过iOS Bark发送通知")
    print("🧹 每小时自动清理旧记录，保留最新30条")
    print("\n按 Ctrl+C 停止监控...")
    
    # 初始化最后清理时间
    last_cleanup_time = time.time()
    
    try:
        while True:
            print("\n" + "="*50)
            print(f"运行时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            print("="*50)
            
            # 检查是否需要清理记录（每小时一次）
            current_time = time.time()
            if current_time - last_cleanup_time >= 3600:  # 3600秒 = 1小时
                print("\n⏰ 执行每小时清理...")
                cleanup_records()
                last_cleanup_time = current_time
            
            # 运行主程序
            main()
            
            # 等待1分钟（60秒）
            print(f"\n⏳ 等待1分钟后再次检查...")
            time.sleep(60)
            
    except KeyboardInterrupt:
        print("\n\n✅ 成绩监控系统已停止")
    except Exception as e:
        print(f"\n\n❌ 监控系统发生错误: {e}")
        import traceback
        traceback.print_exc()
        
        # 发送系统错误通知
        error_title = "⚠️  成绩监控系统错误"
        error_content = f"系统发生严重错误：{str(e)}"
        send_bark_notification(error_title, error_content)
