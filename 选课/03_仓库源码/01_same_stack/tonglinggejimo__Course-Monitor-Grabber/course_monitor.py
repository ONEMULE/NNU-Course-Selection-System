import requests
import time
import subprocess
import os
import sys
import json

import ddddocr

# Configuration
BASE_URL = "https://xsxk.cuc.edu.cn/xsxkapp/sys/xsxkapp"
LOGIN_URL = f"{BASE_URL}/student/check/login.do"
VCODE_URL = f"{BASE_URL}/student/4/vcode.do"
VCODE_IMG_URL = f"{BASE_URL}/student/vcode/image.do"

GRAB_URL = f"{BASE_URL}/elective/volunteer.do"

# Course Constants (Defaults, can be overwritten)
BATCH_CODE = ""
TARGET_COURSE_ID = "" # Computer Vision
CLASS_TYPE = "TJKC"

# User Credentials (HARDCODED FOR DEMO - REPLACE OR LOAD SECURELY)
USERNAME = "" # Extracted from logs


class CourseMonitor:
    # Response codes/messages that indicate an expired or invalid session
    AUTH_EXPIRED_INDICATORS = ["未登录", "登录过期", "token", "Token", "SESSION", "session", "超时", "失效", "非法请求", "身份不一致"]
    AUTH_EXPIRED_CODES = {"302"}

    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.session = requests.Session()
        # Common headers
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest"
        })
        self.ocr = ddddocr.DdddOcr(show_ad=False)
        self.logged_in = False

    def encrypt_password(self, password):
        """Run the Node.js script to encrypt the password."""
        try:
            result = subprocess.run(
                ["node", "login_encrypt.js", password],
                capture_output=True,
                text=True,
                check=True,
                cwd=os.path.dirname(os.path.abspath(__file__))
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            print(f"Error encrypting password: {e.stderr}")
            sys.exit(1)

    def get_captcha(self):
        """Get the vtoken and download the captcha image."""
        timestamp = int(time.time() * 1000)
        try:
            # 1. Get vtoken
            resp = self.session.get(f"{VCODE_URL}?timestamp={timestamp}")
            resp.raise_for_status()
            data = resp.json()
            if data['code'] != '1':
                print(f"Failed to get vtoken: {data}")
                return None, None, None
            
            vtoken = data['data']['token']
            
            # 2. Download Image
            img_resp = self.session.get(f"{VCODE_IMG_URL}?vtoken={vtoken}")
            img_resp.raise_for_status()
            
            # Save for debugging, but we will mostly use bytes directly
            with open("captcha.jpg", "wb") as f:
                f.write(img_resp.content)
            
            return vtoken, img_resp.content
        except Exception as e:
            print(f"Error getting captcha: {e}")
            return None, None

    def login(self):
        """Perform the login flow with retry logic."""
        print("Starting login process...")
        
        # Expectation: Password encryption is deterministic/static for this site
        # We compute it once to avoid spawning node process repeatedly
        encrypted_pwd = self.encrypt_password(self.password)
        
        retry_count = 0
        while True:
            retry_count += 1
            if retry_count > 1:
                print(f"Login attempt #{retry_count}...")
            
            # 1. Get Captcha
            vtoken, img_bytes = self.get_captcha()
            if not vtoken:
                print("Failed to get captcha, retrying in 2 seconds...")
                time.sleep(2)
                continue
                
            # 2. Automated OCR
            verify_code = self.ocr.classification(img_bytes)
            print(f"OCR Recognized Code: {verify_code}")
    
            # 3. Send Login Request
            timestamp = int(time.time() * 1000)
            params = {
                "timestrap": timestamp,
                "loginName": self.username,
                "loginPwd": encrypted_pwd,
                "verifyCode": verify_code,
                "vtoken": vtoken
            }
            
            try:
                resp = self.session.get(LOGIN_URL, params=params)
                resp.raise_for_status()
                result = resp.json()
                
                if result.get('code') == '1':
                    print("Login successful!")
                    print(f"Welcome {result['data']['name']}")
                    self.token = result['data']['token']
                    # Update session headers with the token for subsequent requests
                    self.session.headers.update({"token": self.token})
                    self.logged_in = True
                    return True
                else:
                    msg = result.get('msg', 'Unknown error')
                    print(f"Login failed: {msg}")
                    # If it's a captcha error, we just loop again immediately (or with small delay)
                    # If it's a password error, we still loop but maybe user should know?
                    # For now, infinite loop as requested "until login success"
                    time.sleep(1)
                    
            except Exception as e:
                print(f"Login request error: {e}")
                time.sleep(2)
            
            # Prevent rapid-fire looping in case of severe network issues
            time.sleep(0.5)

    def _is_auth_expired(self, result):
        """Check if an API response indicates the session/token has expired."""
        if result is None:
            return True
        code = str(result.get('code', ''))
        msg = str(result.get('msg', ''))
        # Specific error codes that mean auth expired
        if code in self.AUTH_EXPIRED_CODES:
            return True
        # Treat non-'1' codes with auth-related messages as expired
        if code != '1':
            for indicator in self.AUTH_EXPIRED_INDICATORS:
                if indicator in msg or indicator in code:
                    return True
        return False

    def ensure_logged_in(self):
        """Re-login only if needed. Returns True if session is valid."""
        if self.logged_in:
            return True
        print("[Session] Token expired or not logged in, re-logging in...")
        return self.login()

    def get_batch_code(self):
        """
        Try to get the batch code. 
        For now, we'll try to fetch student status or just return the hardcoded one 
        if we can't find it dynamically (since the capture data was ambiguous on source).
        """
        # TODO: Implement dynamic fetching from /elective/studentstatus.do if possible.
        # Current analysis suggests it might be hard to get without a proper flow.
        # We will use the hardcoded one but allow user to override if needed.
        return BATCH_CODE

    def list_courses(self, batch_code):
        """Fetch list of available courses."""
        print("Fetching course list...")
        # URL identified from CSV traffic analysis
        url = f"{BASE_URL}/elective/recommendedCourse.do"
        
        # Payload matching the successful request in CSV
        payload = {
            "querySetting": json.dumps({
                "data": {
                    "studentCode": self.username,
                    "campus": "11", # Correct campus code for main campus
                    "electiveBatchCode": batch_code,
                    "isMajor": "1",
                    "teachingClassType": "TJKC",
                    "checkConflict": "2",
                    "checkCapacity": "2",
                    "queryContent": ""
                },
                "pageSize": "100",
                "pageNumber": "0",
                "order": ""
            })
        }
        
        try:
            resp = self.session.post(url, data=payload)
            # print(f"DEBUG: Course list response: {resp.text[:200]}...") # Debug
            
            data = resp.json()
            if data.get('code') != '1':
                print(f"Failed to fetch courses: {data.get('msg')}")
                return []
                
            return data.get('dataList', [])
        except Exception as e:
            print(f"Error fetching courses: {e}")
            return []

    def interactive_selection(self):
        """Interactive course selection."""
        batch_code = self.get_batch_code()
        print(f"Using Batch Code: {batch_code}")
        
        courses = self.list_courses(batch_code)
        if not courses:
            print("No courses found or failed to fetch. Using default target.")
            return TARGET_COURSE_ID, batch_code, CLASS_TYPE
            
        print("\nAvailable Courses:")
        print(f"{'IDX':<5} {'Name':<20} {'Teacher':<10} {'ID':<25} {'Spots':<10} {'Type':<5}")
        print("-" * 80)
        
        valid_courses = []
        for i, c in enumerate(courses):
            c_name = c.get('courseName', 'Unknown')
            # The structure contains a list of teaching classes (sections)
            tc_list = c.get('tcList', [])
            
            for tc in tc_list:
                c_teacher = tc.get('teacherName', 'Unknown')
                c_id = tc.get('teachingClassID', 'Unknown') 
                c_capacity = tc.get('classCapacity', 'N/A')
                c_selected = tc.get('numberOfSelected', 'N/A')
                spots_str = f"{c_selected}/{c_capacity}"
                
                # Check for specific type or default to TJKC
                # Debug output didn't show type in tcList, using generic default for now
                c_type = "TJKC" 
                
                idx_str = str(len(valid_courses))
                print(f"{idx_str:<5} {c_name:<20} {c_teacher:<10} {c_id:<25} {spots_str:<10} {c_type:<5}")
                valid_courses.append({
                    "id": c_id,
                    "type": c_type,
                    "name": c_name,
                    "batch": batch_code 
                })
            
        print("-" * 80)
        selection = input("Enter index of course to grab (or 'q' to quit, 'd' for default): ")
        
        if selection.lower() == 'd':
            return TARGET_COURSE_ID, batch_code, CLASS_TYPE
        if selection.lower() == 'q':
            sys.exit(0)
            
        try:
            idx = int(selection)
            if 0 <= idx < len(valid_courses):
                selected = valid_courses[idx]
                print(f"Selected: {selected['name']} ({selected['id']})")
                return selected['id'], batch_code, selected['type']
            else:
                print("Invalid index. Using default.")
        except ValueError:
            print("Invalid input. Using default.")
            
        return TARGET_COURSE_ID, batch_code, CLASS_TYPE

    def run_monitor(self):
        """Main execution flow."""
        if not self.login():
            return

        print("Login success.")
        target_id, batch_code, class_type = self.interactive_selection()

        if target_id:
            # First immediate attempt
            result = self.grab_course(target_id, batch_code, class_type)
            # If auth expired on first attempt, re-login and retry once
            if result == "auth_expired":
                if self.ensure_logged_in():
                    self.grab_course(target_id, batch_code, class_type)

            # Periodic monitoring setup
            while True:
                try:
                    interval_str = input("\nEnter monitoring interval in minutes (0 to exit): ").strip()
                    interval = float(interval_str)
                    if interval <= 0:
                        break

                    print(f"Starting periodic monitoring for course {target_id} every {interval} minutes...")
                    print("Press Ctrl+C to stop.")

                    while True:
                        print(f"\nWaiting {interval} minutes before next attempt...")
                        time.sleep(interval * 60)

                        # Ensure we have a valid session (re-login only if expired)
                        if not self.ensure_logged_in():
                            print("[Periodic Check] Login failed, skipping this attempt.")
                            continue

                        result = self.grab_course(target_id, batch_code, class_type)
                        if result == "auth_expired":
                            # Token just expired, re-login and retry immediately
                            print("[Periodic Check] Token expired mid-request, re-logging in...")
                            if self.ensure_logged_in():
                                self.grab_course(target_id, batch_code, class_type)
                            else:
                                print("[Periodic Check] Re-login failed, will retry next cycle.")

                except ValueError:
                    print("Invalid input. Please enter a number.")
                except KeyboardInterrupt:
                    print("\nMonitoring stopped by user.")
                    break

    def grab_course(self, target_id=TARGET_COURSE_ID, batch_code=BATCH_CODE, class_type=CLASS_TYPE):
        """Attempt to grab the specific course. Returns 'success', 'already', 'auth_expired', or 'failed'."""
        print(f"Preparing to grab course [{target_id}]...")

        # Construct the payload
        payload_data = {
            "operationType": "1",
            "studentCode": self.username,
            "electiveBatchCode": batch_code,
            "teachingClassId": target_id,
            "isMajor": "1",
            "campus": "11", # Corrected from "1" based on error "campus mismatch" & CSV
            "teachingClassType": class_type
        }

        # The API expects 'addParam' as a JSON string within the form data
        data = {
            "addParam": json.dumps({"data": payload_data})
        }

        try:
            resp = self.session.post(GRAB_URL, data=data)
            print(f"Request sent. HTTP Status: {resp.status_code}")

            # HTTP 401/403 likely means auth expired
            if resp.status_code in (401, 403):
                print("[Session] HTTP status indicates auth expired.")
                self.logged_in = False
                return "auth_expired"

            try:
                result = resp.json()
                print(f"Response: {json.dumps(result, indent=2, ensure_ascii=False)}")

                # Check for auth expiration in the response body
                if self._is_auth_expired(result):
                    print("[Session] Response indicates auth expired.")
                    self.logged_in = False
                    return "auth_expired"

                if result.get('code') == '1':
                    print(">>> SUCCESS: Course added successfully! <<<")
                    return "success"
                elif "已经存在选课结果中" in str(result):
                    print(">>> INFO: Course already selected. <<<")
                    return "already"
                else:
                    print(f">>> FAILED: {result.get('msg', 'Unknown error')} <<<")
                    return "failed"

            except json.JSONDecodeError:
                print(f"Could not parse response JSON. Raw text: {resp.text}")
                return "failed"

        except Exception as e:
            print(f"Error during course grab: {e}")
            return "failed"

if __name__ == "__main__":
    # Check if password is provided
    if len(sys.argv) > 1:
        pwd = sys.argv[1]
    else:
        # Ask user for password if not provided
        pwd = input("Enter Password: ")
    
    monitor = CourseMonitor(USERNAME, pwd)
    monitor.run_monitor()

