import requests

from utils.cas_cache_utils import get_mod_auth_cas
from utils.common_utils import get_ehall_url
from utils.request_utils import default_header


def get_user_info(school_name: str, token: str) -> tuple[dict, int]:
    # check if school is supported
    ehall_url = get_ehall_url(school_name)

    mod_auth_cas = get_mod_auth_cas(school_name, token)
    if mod_auth_cas is None:
        return {'status': 'error', 'message': 'Failed to get user info. authToken is probably invalid.'}, 401
    # get user info
    s = requests.Session()
    s.cookies.set('MOD_AUTH_CAS', mod_auth_cas)
    s.headers.update(default_header)

    query_url = ehall_url + '//jsonp/ywtb/info/getUserInfoAndSchoolInfo.json'
    response = s.get(query_url)

    # check if the response is valid, and get 'username', 'userid', 'userType', 'userDepartment',  'userSex'
    if response.status_code != 200:
        return {'status': 'retry', 'message': 'Failed to get user info.Please try again'}, 402
    try:
        user_info_orig = response.json()['data']
    except Exception as e:
        return {'status': 'retry', 'message': f'Unknown error.Please try again'}, 402
    # if MOD_AUTH_CAS is invalid, the values in "data" will be null
    if user_info_orig['userName'] is None:
        return {'status': 'retry', 'message': 'Unexpected behavior happened.Please try again'}, 402

    user_info: dict = {'status': 'OK', 'message': 'User info retrieved successfully',
                       'data': {
                           'userName': user_info_orig['userName'], 'userId': user_info_orig['userId'],
                           'userType': user_info_orig['userTypeName'],
                           'userDepartment': user_info_orig['userDepartment'],
                           'userSex': user_info_orig['userSex']
                       }
                       }

    return user_info, 200
