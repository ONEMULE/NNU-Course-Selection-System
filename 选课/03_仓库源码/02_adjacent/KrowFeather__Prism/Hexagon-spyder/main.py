from flask import Flask, request, jsonify, abort
from flask_cors import CORS
from service import *

app = Flask(__name__)
CORS(app)


@app.route("/", methods=["GET"])
def root():
    return jsonify({"message": "Hexagon抢课系统 API", "version": "1.0.0"})


@app.route("/login", methods=["POST"])
def api_login():
    """登录接口"""
    data = request.get_json()
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({
            "success": False,
            "message": "请提供用户名和密码"
        }), 400

    username = data['username']
    password = data['password']

    token, WEU, JSESSIONID = None, None, None
    retry = 20
    while retry > 0:
        token, WEU, JSESSIONID = login(username, password)
        if token:
            break
        retry -= 1
        time.sleep(1)

    if token:
        return jsonify({
            "success": True,
            "token": token,
            "WEU": WEU,
            "JSESSIONID": JSESSIONID
        })
    else:
        return jsonify({
            "success": False,
            "message": "登录失败，请检查用户名和密码"
        })


@app.route("/select-class", methods=["POST"])
def api_select_class():
    """选课接口"""
    data = request.get_json()

    if not data:
        return jsonify({
            "success": False,
            "message": "请提供选课信息"
        }), 400

    required_fields = ['username', 'password', 'electiveBatchCode', 'teachingClassId']
    for field in required_fields:
        if field not in data:
            return jsonify({
                "success": False,
                "message": f"缺少必需字段: {field}"
            }), 400

    result, message = select_class(
        username=data['username'],
        password=data['password'],
        elective_batch_code=data['electiveBatchCode'],
        teaching_class_id=data['teachingClassId'],
        is_major=data.get('isMajor', '1'),
        campus=data.get('campus', '02'),
        teaching_class_type=data.get('teachingClassType', 'XGXK'),
        operation_type=data.get('operationType', '1')
    )

    if result:
        return jsonify({
            "success": True,
            "message": message,
            "result": result
        })
    else:
        return jsonify({
            "success": False,
            "message": message
        })


@app.route("/drop-class", methods=["POST"])
def api_drop_class():
    """退课接口"""
    data = request.get_json()

    if not data:
        return jsonify({
            "success": False,
            "message": "请提供退课信息"
        }), 400

    required_fields = ['username', 'password', 'electiveBatchCode', 'teachingClassId']
    for field in required_fields:
        if field not in data:
            return jsonify({
                "success": False,
                "message": f"缺少必需字段: {field}"
            }), 400

    result, message = drop_class(
        username=data['username'],
        password=data['password'],
        elective_batch_code=data['electiveBatchCode'],
        teaching_class_id=data['teachingClassId'],
        is_major=data.get('isMajor', '1')
    )

    if result:
        return jsonify({
            "success": True,
            "message": message,
            "result": result
        })
    else:
        return jsonify({
            "success": False,
            "message": message
        })


@app.route("/send-email", methods=["POST"])
def api_send_email():
    """发送邮件接口"""
    data = request.get_json()

    if not data or 'email_user' not in data or 'email_auth' not in data:
        return jsonify({
            "success": False,
            "message": "请提供邮箱地址和授权码"
        }), 400

    success = send_email(
        email_user=data['email_user'],
        email_auth=data['email_auth'],
        subject=data.get('subject', '选课成功'),
        message=data.get('message', '选课成功')
    )

    if success:
        return jsonify({
            "success": True,
            "message": "邮件发送成功"
        })
    else:
        return jsonify({
            "success": False,
            "message": "邮件发送失败，请检查邮箱配置"
        })


@app.route("/sessions", methods=["GET"])
def get_sessions():
    """获取当前所有会话（仅用于调试）"""
    return jsonify({"sessions": list(user_sessions.keys())})


@app.route("/sessions/<username>", methods=["DELETE"])
def delete_session(username: str):
    """删除指定用户的会话"""
    if username in user_sessions:
        del user_sessions[username]
        return jsonify({"message": f"已删除用户 {username} 的会话"})
    else:
        abort(404, description="会话不存在")


@app.route("/get-batches", methods=["POST"])
def api_get_batches():
    """获取选课批次接口"""
    data = request.get_json()
    
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({
            "success": False,
            "message": "请提供用户名和密码"
        }), 400
    
    username = data['username']
    password = data['password']
    
    result, message = get_batches(username, password)
    
    if result:
        return jsonify({
            "success": True,
            "message": message,
            "data": result
        })
    else:
        return jsonify({
            "success": False,
            "message": message
        })


@app.route("/get-sys-params", methods=["POST"])
def api_get_sys_params():
    """获取系统参数接口（包含课程类型名称）"""
    data = request.get_json()
    
    if not data or 'username' not in data:
        return jsonify({
            "success": False,
            "message": "请提供用户名"
        }), 400
    
    username = data['username']
    password = data.get('password', '')
    
    result, message = get_sys_params(username, password)
    
    if result:
        return jsonify({
            "success": True,
            "message": message,
            "data": result
        })
    else:
        return jsonify({
            "success": False,
            "message": message
        })


@app.route("/get-selected-courses", methods=["POST"])
def api_get_selected_courses():
    """获取用户已选课程接口"""
    data = request.get_json()
    
    if not data or 'username' not in data or 'electiveBatchCode' not in data:
        return jsonify({
            "success": False,
            "message": "请提供用户名和选课批次代码"
        }), 400
    
    username = data['username']
    password = data.get('password', '')
    elective_batch_code = data['electiveBatchCode']
    
    # 如果用户未登录，需要密码
    if username not in user_sessions and not password:
        return jsonify({
            "success": False,
            "message": "用户未登录，请提供密码"
        }), 400
    
    result, message = get_selected_courses(username, elective_batch_code, password)
    
    if result:
        return jsonify({
            "success": True,
            "message": message,
            "data": result.get('dataList', [])
        })
    else:
        return jsonify({
            "success": False,
            "message": message
        })


@app.route("/get-courses", methods=["POST"])
def api_get_courses():
    """获取课程列表接口"""
    data = request.get_json()
    
    if not data or 'username' not in data or 'electiveBatchCode' not in data:
        return jsonify({
            "success": False,
            "message": "请提供用户名和选课批次代码"
        }), 400
    
    username = data['username']
    password = data.get('password', '')
    elective_batch_code = data['electiveBatchCode']
    
    # 如果用户未登录，需要密码
    if username not in user_sessions and not password:
        return jsonify({
            "success": False,
            "message": "用户未登录，请提供密码"
        }), 400
    
    result, message = get_courses(
        username=username,
        elective_batch_code=elective_batch_code,
        is_major=data.get('isMajor', '1'),
        campus=data.get('campus', '02'),
        teaching_class_type=data.get('teachingClassType', 'XGXK'),
        query_content=data.get('queryContent', ''),
        check_conflict=data.get('checkConflict', '2'),
        check_capacity=data.get('checkCapacity', '2')
    )
    
    if result:
        return jsonify({
            "success": True,
            "message": message,
            "data": result
        })
    else:
        return jsonify({
            "success": False,
            "message": message
        })


@app.route("/start-grab-course", methods=["POST"])
def api_start_grab_course():
    """启动轮询抢课接口"""
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "message": "请提供抢课信息"
        }), 400
    
    required_fields = ['username', 'password', 'electiveBatchCode', 'teachingClassId']
    for field in required_fields:
        if field not in data:
            return jsonify({
                "success": False,
                "message": f"缺少必需字段: {field}"
            }), 400
    
    task_id = start_grab_course(
        username=data['username'],
        password=data['password'],
        elective_batch_code=data['electiveBatchCode'],
        teaching_class_id=data['teachingClassId'],
        is_major=data.get('isMajor', '1'),
        campus=data.get('campus', '02'),
        teaching_class_type=data.get('teachingClassType', 'XGXK'),
        select_rate=data.get('selectRate', 2),
        email_user=data.get('emailUser'),
        email_auth=data.get('emailAuth'),
        email_msg=data.get('emailMsg', '选课成功')
    )
    
    if task_id is None:
        return jsonify({
            "success": False,
            "message": "该课程已选课成功，无需再次抢课"
        }), 400
    
    return jsonify({
        "success": True,
        "message": "抢课任务已启动",
        "task_id": task_id
    })


@app.route("/stop-grab-course", methods=["POST"])
def api_stop_grab_course():
    """停止轮询抢课接口"""
    data = request.get_json()
    
    if not data or 'task_id' not in data:
        return jsonify({
            "success": False,
            "message": "请提供任务ID"
        }), 400
    
    task_id = data['task_id']
    success = stop_grab_course(task_id)
    
    if success:
        return jsonify({
            "success": True,
            "message": "抢课任务已停止"
        })
    else:
        return jsonify({
            "success": False,
            "message": "任务不存在或已停止"
        }), 404


@app.route("/grab-course-status/<task_id>", methods=["GET"])
def api_get_grab_course_status(task_id: str):
    """获取轮询抢课任务状态接口"""
    status = get_grab_task_status(task_id)
    
    if status:
        return jsonify({
            "success": True,
            "data": status
        })
    else:
        return jsonify({
            "success": False,
            "message": "任务不存在"
        }), 404


@app.route("/grab-course-status", methods=["GET"])
def api_get_all_grab_course_status():
    """获取所有轮询抢课任务状态接口"""
    tasks = get_all_grab_tasks()
    
    return jsonify({
        "success": True,
        "data": tasks
    })


if __name__ == "__main__":
    app.run(debug=True)
