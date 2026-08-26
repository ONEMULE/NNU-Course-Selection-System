import requests

from utils.cas_cache_utils import get_mod_auth_cas
from utils.common_utils import get_ehall_url, get_ehallapp_url
from utils.request_utils import default_header


def get_course_table(school_name: str, token: str, semester: str) -> tuple[dict, int]:
    ehallapp_url = get_ehallapp_url(school_name)
    ehall_url = get_ehall_url(school_name)

    mod_auth_cas = get_mod_auth_cas(school_name, token)
    if mod_auth_cas is None:
        return {'status': 'error', 'message': 'Failed to get course table. authToken is probably invalid.'}, 401

    s = requests.Session()
    s.cookies.set('MOD_AUTH_CAS', mod_auth_cas)
    s.headers.update(default_header)
    if 'Referer' in s.headers:
        del s.headers['Referer']

    query_weu_url = ehall_url + '/appShow?appId=4770397878132218'
    response = s.get(query_weu_url)
    if response.status_code != 200:
        return {'status': 'retry', 'message': 'Failed to get course table.Please try again'}, 402

    s.headers['Accept'] = 'application/json, text/javascript, */*; q=0.01'
    # query not arranged location courses
    query_no_location_url = ehallapp_url + '/jwapp/sys/wdkb/nnuWdkbController/queryXskbForNnu.do'
    if semester == "":
        query_semester_url = ehallapp_url + '/jwapp/sys/wdkb/modules/jshkcb/dqxnxq.do'
        response = s.get(query_semester_url)
        semester = response.json()['datas']['dqxnxq']['rows'][0]['DM']

    query_no_location_data = {
        'requestParamStr': f'{{"XNXQDM":"{semester}","SKZC":1}}'
    }
    response = s.post(query_no_location_url, data=query_no_location_data)
    response_list1 = transfer_json_data(response.json())
    result = {'status': 'OK', 'message': 'Course table retrieved successfully',
              'data': {'not_arranged': response_list1, 'arranged': []}}

    query_course_table_url = ehallapp_url + '/jwapp/sys/wdkb/modules/xskcb/cxxszhxqkb.do'
    query_course_table_data = {
        'XNXQDM': semester,
        '*order': '+KSJC'
    }

    response = s.post(query_course_table_url, data=query_course_table_data)
    response_list2 = transfer_json_data(response.json(), False)
    result['data']['arranged'] = response_list2
    return result, 200


def transfer_json_data(json_data: dict, isnolocation: bool = True) -> list:
    """transfer the json data to a list of dict"""
    if isnolocation:
        data = json_data['datas']['queryXskbForNnu']['rows']
        result = []
        for item in data:
            result.append({
                'courseName': item['KCM'],
                'courseID': item['KCH'],
                'classID': item['JXBID'],
                'teacher': item['SKJS'],
                'week': item['SKZC'],
                'credit': item['XF'],
                'creditHour': item['XS'],
                'semester': item['XNXQDM']
            })
        return result
    else:
        data = json_data['datas']['cxxszhxqkb']['rows']
        result = []
        for item in data:
            if item['YPSJDD'] is None:
                continue
            time = extract_weekday_time(item['YPSJDD'])
            result.append({
                'courseName': item['KCM'],
                'courseID': item['KCH'],
                'classID': item['JXBID'],
                'teacher': item['SKJS'],
                'classroom': item['JASMC'],
                'week': item['ZCMC'],
                'time': time,
                'credit': item['XF'],
                'creditHour': item['XS'],
                'semester': item['XNXQDM']
            })
        return result


def extract_weekday_time(data):
    weekday_map = {
        "一": "1",
        "二": "2",
        "三": "3",
        "四": "4",
        "五": "5",
        "六": "6",
        "日": "7"
    }

    segments = data.split(",")
    results = []

    for segment in segments:
        weekday = ""
        for key, value in weekday_map.items():
            if f"星期{key}" in segment:
                weekday = value
                break

        time_info = segment.split(" ")[2].split("节")[0]

        results.append(f"{weekday}:{time_info}")

    result_str = ",".join(results)

    return result_str
