import requests
import json
import six
from six.moves.urllib.parse import urlparse
from distutils.version import LooseVersion
from pyramid.response import Response
from pyramid.testing import setUp as PyramidSetUp
from webtest import TestApp
from webtest.response import TestResponse
from webob.headers import ResponseHeaders
from magpie import __meta__, services, magpiectl
from magpie.common import get_settings_from_config_ini
from magpie.constants import get_constant
from typing import AnyStr, Dict, List, Optional, Tuple, Union

OptionalStringType = six.string_types + tuple([type(None)])
HeadersType = Union[Dict[AnyStr, AnyStr], List[Tuple[AnyStr, AnyStr]]]
CookiesType = Union[Dict[AnyStr, AnyStr], List[Tuple[AnyStr, AnyStr]]]
OptionalHeaderCookiesType = Union[Tuple[None, None], Tuple[HeadersType, CookiesType]]
TestAppOrUrlType = Union[AnyStr, TestApp]
ResponseType = Union[TestResponse, Response]


def config_setup_from_ini(config_ini_file_path):
    settings = get_settings_from_config_ini(config_ini_file_path)
    config = PyramidSetUp(settings=settings)
    return config


def get_test_magpie_app():
    # parse settings from ini file to pass them to the application
    config = config_setup_from_ini(get_constant('MAGPIE_INI_FILE_PATH'))
    config.include('ziggurat_foundations.ext.pyramid.sign_in')
    config.include('ziggurat_foundations.ext.pyramid.get_user')
    config.registry.settings['magpie.db_migration_disabled'] = True
    # scan dependencies
    config.include('magpie')
    # create the test application
    app = TestApp(magpiectl.main({}, **config.registry.settings))
    return app


def get_hostname(app_or_url):
    if isinstance(app_or_url, TestApp):
        app_or_url = get_constant('MAGPIE_URL', settings=app_or_url.app.registry.settings, settings_name='magpie.url')
    return urlparse(app_or_url).hostname


def get_headers(app_or_url, header_dict):
    if isinstance(app_or_url, TestApp):
        return header_dict.items()
    return header_dict


def get_header(header_name, header_container):
    # type: (AnyStr, Optional[Union[HeadersType, ResponseHeaders]]) -> Union[AnyStr, None]
    if header_container is None:
        return None
    headers = header_container
    if isinstance(headers, ResponseHeaders):
        headers = dict(headers)
    if isinstance(headers, dict):
        headers = header_container.items()
    header_name = header_name.lower().replace('-', '_')
    for h, v in headers:
        if h.lower().replace('-', '_') == header_name:
            return v
    return None


def get_response_content_types_list(response):
    return [ct.strip() for ct in response.headers['Content-Type'].split(';')]


def get_json_body(response):
    if isinstance(response, TestResponse):
        return response.json
    return response.json()


def get_service_types_for_version(version):
    available_service_types = set(services.service_type_dict.keys())
    if LooseVersion(version) <= LooseVersion('0.6.1'):
        available_service_types = available_service_types - {'access'}
    return list(available_service_types)


def test_request(app_or_url, method, path, timeout=5, allow_redirects=True, **kwargs):
    """
    Calls the request using either a `webtest.TestApp` instance or a `requests` instance from a string URL.
    :param app_or_url: `webtest.TestApp` instance of the test application or remote server URL to call with `requests`
    :param method: request method (GET, POST, PUT, DELETE)
    :param path: test path starting at base path
    :param timeout: `timeout` to pass down to `request`
    :param allow_redirects: `allow_redirects` to pass down to `request`
    :return: response of the request
    """
    method = method.upper()
    status = kwargs.pop('status', None)

    # obtain json body from any json/data/body/params kw and empty {} if not specified
    # reapply with the expected webtest/requests method kw afterward
    json_body = None
    for kw in ['json', 'data', 'body', 'params']:
        json_body = kwargs.get(kw, json_body)
        if kw in kwargs:
            kwargs.pop(kw)
    json_body = json_body or {}

    if isinstance(app_or_url, TestApp):
        # remove any 'cookies' keyword handled by the 'TestApp' instance
        if 'cookies' in kwargs:
            cookies = kwargs.pop('cookies')
            if cookies and not app_or_url.cookies:
                app_or_url.cookies.update(cookies)

        # obtain Content-Type header if specified to ensure it is properly applied
        kwargs['content_type'] = get_header('Content-Type', kwargs.get('headers'))

        # convert JSON body as required
        kwargs['params'] = json_body
        if json_body is not None:
            kwargs.update({'params': json.dumps(json_body, cls=json.JSONEncoder)})
        if status and status >= 300:
            kwargs.update({'expect_errors': True})
        # noinspection PyProtectedMember
        resp = app_or_url._gen_request(method, path, **kwargs)
        # automatically follow the redirect if any and evaluate its response
        max_redirect = kwargs.get('max_redirects', 5)
        while 300 <= resp.status_code < 400 and max_redirect > 0:
            resp = resp.follow()
            max_redirect -= 1
        assert max_redirect >= 0, "Maximum follow redirects reached."
        # test status accordingly if specified
        assert resp.status_code == status or status is None, "Response not matching the expected status code."
        return resp
    else:
        # remove keywords specific to TestApp
        kwargs.pop('expect_errors', None)

        kwargs['json'] = json_body
        url = '{url}{path}'.format(url=app_or_url, path=path)
        return requests.request(method, url, timeout=timeout, allow_redirects=allow_redirects, **kwargs)


def get_session_user(app_or_url, headers=None):
    # type: (TestAppOrUrlType, Optional[HeadersType]) -> ResponseType
    if not headers:
        headers = get_headers(app_or_url, {'Accept': 'application/json', 'Content-Type': 'application/json'})
    if isinstance(app_or_url, TestApp):
        resp = app_or_url.get('/session', headers=headers)
    else:
        resp = requests.get('{}/session'.format(app_or_url), headers=headers)
    if resp.status_code != 200:
        raise Exception('cannot retrieve logged in user information')
    return resp


def check_or_try_login_user(app_or_url,                     # type: TestAppOrUrlType
                            username=None,                  # type: Optional[AnyStr]
                            password=None,                  # type: Optional[AnyStr]
                            provider='ziggurat',            # type: Optional[AnyStr]
                            headers=None,                   # type: Optional[Dict[AnyStr, AnyStr]]
                            use_ui_form_submit=False,       # type: Optional[bool]
                            version=__meta__.__version__,   # type: Optional[AnyStr]
                            ):                              # type: (...) -> OptionalHeaderCookiesType
    """
    Verifies that the required user is already logged in (or none is if username=None), or tries to login him otherwise.
    Validates that the logged user (if any), matched the one specified with `username`.

    :param app_or_url: instance of the test application or remote server URL to call
    :param username: name of the user to login or None otherwise
    :param password: password to use for login if the user was not already logged in
    :param provider: provider string to use for login (default: ziggurat, ie: magpie's local signin)
    :param headers: headers to include in the test request
    :param use_ui_form_submit: use Magpie UI login 'form' to obtain cookies
        (required for local `WebTest.App` login, ignored by requests using URL)
    :param version: server or local app version to evaluate responses with backward compatibility
    :return: headers and cookies of the user session or (None, None)
    :raise: Exception on any login failure as required by the caller's specifications (username/password)
    """

    headers = headers or {}
    resp = get_session_user(app_or_url, headers)
    body = get_json_body(resp)

    resp_cookies = None
    auth = body.get('authenticated', False)
    if auth is False and username is None:
        return None, None
    if auth is False and username is not None:
        data = {'user_name': username, 'password': password, 'provider_name': provider}

        if isinstance(app_or_url, TestApp):
            if use_ui_form_submit:
                resp = app_or_url.get(url='/ui/login')
                form = resp.forms['login_internal']
                form['user_name'] = username
                form['password'] = password
                form['provider_name'] = provider
                resp = form.submit('submit')
                resp_cookies = app_or_url.cookies    # automatically set by form submit
            else:
                resp = app_or_url.post_json('/signin', data, headers=headers)
                resp_cookies = resp.cookies
        else:
            resp = requests.post('{}/signin'.format(app_or_url), json=data, headers=headers)
            resp_cookies = resp.cookies

        # response OK (200) if directly from API /signin
        # response Found (302) if redirected UI /login
        if resp.status_code < 400:
            return resp.headers, resp_cookies

    if auth is True:
        if LooseVersion(version) >= LooseVersion('0.6.3'):
            logged_user = body.get('user', {}).get('user_name', '')
        else:
            logged_user = body.get('user_name', '')
        if username != logged_user:
            raise Exception("invalid user")
        if isinstance(app_or_url, TestApp):
            resp_cookies = app_or_url.cookies
        else:
            resp_cookies = resp.cookies

    return resp.headers, resp_cookies


def check_or_try_logout_user(app_or_url):
    # type: (TestAppOrUrlType) -> None
    """
    Verifies that any user is logged out, or tries to logout him otherwise.

    :param app_or_url: instance of the test application or remote server URL to call
    :raise: Exception on any logout failure or incapability to validate logout
    """

    def _is_logged_out():
        resp = get_session_user(app_or_url)
        body = get_json_body(resp)
        auth = body.get('authenticated', False)
        return not auth

    if _is_logged_out():
        return
    resp_logout = test_request(app_or_url, 'GET', '/ui/logout', allow_redirects=True)
    if isinstance(app_or_url, TestApp):
        app_or_url.reset()  # clear app cookies
    if resp_logout.status_code >= 400:
        raise Exception("cannot validate logout")
    if _is_logged_out():
        return
    raise Exception("logout did not succeed")


def format_test_val_ref(val, ref, pre='Fail', msg=None):
    _msg = '({0}) Test value: `{1}`, Reference value: `{2}`'.format(pre, val, ref)
    if isinstance(msg, six.string_types):
        _msg = '{}\n{}'.format(msg, _msg)
    return _msg


def all_equal(iter_val, iter_ref, any_order=False):
    if not (hasattr(iter_val, '__iter__') and hasattr(iter_ref, '__iter__')):
        return False
    if len(iter_val) != len(iter_ref):
        return False
    if any_order:
        return all([it in iter_ref for it in iter_val])
    return all(it == ir for it, ir in zip(iter_val, iter_ref))


def check_all_equal(iter_val, iter_ref, any_order=False, msg=None):
    r_it_val = repr(iter_val)
    r_it_ref = repr(iter_ref)
    assert all_equal(iter_val, iter_ref, any_order), format_test_val_ref(r_it_val, r_it_ref, pre='Equal Fail', msg=msg)


def check_val_equal(val, ref, msg=None):
    assert isinstance(ref, null) or val == ref, format_test_val_ref(val, ref, pre='Equal Fail', msg=msg)


def check_val_not_equal(val, ref, msg=None):
    assert isinstance(ref, null) or val != ref, format_test_val_ref(val, ref, pre='Equal Fail', msg=msg)


def check_val_is_in(val, ref, msg=None):
    assert isinstance(ref, null) or val in ref, format_test_val_ref(val, ref, pre='Is In Fail', msg=msg)


def check_val_not_in(val, ref, msg=None):
    assert isinstance(ref, null) or val not in ref, format_test_val_ref(val, ref, pre='Not In Fail', msg=msg)


def check_val_type(val, ref, msg=None):
    assert isinstance(val, ref), format_test_val_ref(val, repr(ref), pre='Type Fail', msg=msg)


def check_response_basic_info(response, expected_code=200, expected_type='application/json', expected_method='GET'):
    """
    Validates basic Magpie API response metadata.

    :param response: response to validate.
    :param expected_code: status code to validate from the response.
    :param expected_type: Content-Type to validate from the response.
    :param expected_method: method 'GET', 'POST', etc. to validate from the response if an error.
    :return: json body of the response for convenience.
    """
    json_body = get_json_body(response)
    check_val_is_in('Content-Type', dict(response.headers), msg="Response doesn't define `Content-Type` header.")
    content_types = get_response_content_types_list(response)
    check_val_equal(response.status_code, expected_code, msg="Response doesn't match expected HTTP status code.")
    check_val_is_in(expected_type, content_types, msg="Response doesn't match expected HTTP Content-Type header.")
    check_val_is_in('code', json_body, msg="Parameter `code` should be in response JSON body.")
    check_val_is_in('type', json_body, msg="Parameter `type` should be in response JSON body.")
    check_val_is_in('detail', json_body, msg="Parameter `detail` should be in response JSON body.")
    check_val_equal(json_body['code'], expected_code, msg="Parameter `code` should match the HTTP status code.")
    check_val_equal(json_body['type'], expected_type, msg="Parameter `type` should match the HTTP Content-Type header.")
    check_val_not_equal(json_body['detail'], '', msg="Parameter `detail` should not be empty.")

    if response.status_code in [401, 404, 500]:
        check_val_is_in('request_url', json_body)
        check_val_is_in('route_name', json_body)
        check_val_is_in('method', json_body)
        check_val_equal(json_body['method'], expected_method)

    return json_body


class null(object):
    """ Represents a null value to differentiate from None. """
    def __repr__(self):
        return '<Null>'


Null = null()


def check_error_param_structure(json_body, param_value=Null, param_name=Null, param_compare=Null,
                                is_param_value_literal_unicode=False, param_compare_exists=False, version=None):
    """
    Validates error response 'param' information based on different Magpie version formats.
    :param json_body: json body of the response to validate.
    :param param_value: expected 'value' of param, not verified if <Null>
    :param param_name: expected 'name' of param, not verified if <Null> or non existing for Magpie version
    :param param_compare: expected 'compare'/'paramCompare' value, not verified if <Null>
    :param is_param_value_literal_unicode: param value is represented as `u'{paramValue}'` for older Magpie version
    :param param_compare_exists: verify that 'compare'/'paramCompare' is in the body, not validating its actual value
    :param version: version of application/remote server to use for format validation, use local Magpie version if None
    :raise failing condition
    """
    check_val_type(json_body, dict)
    check_val_is_in('param', json_body)
    version = version or __meta__.__version__
    if LooseVersion(version) >= LooseVersion('0.6.3'):
        check_val_type(json_body['param'], dict)
        check_val_is_in('value', json_body['param'])
        check_val_is_in('name', json_body['param'])
        check_val_equal(json_body['param']['name'], param_name)
        check_val_equal(json_body['param']['value'], param_value)
        if param_compare_exists:
            check_val_is_in('compare', json_body['param'])
            check_val_equal(json_body['param']['compare'], param_compare)
    else:
        # unicode representation was explicitly returned in value only when of string type
        if is_param_value_literal_unicode and isinstance(param_value, six.string_types):
            param_value = u'u\'{}\''.format(param_value)
        check_val_equal(json_body['param'], param_value)
        if param_compare_exists:
            check_val_is_in('paramCompare', json_body)
            check_val_equal(json_body['paramCompare'], param_compare)


def check_post_resource_structure(json_body, resource_name, resource_type, resource_display_name, version=None):
    """
    Validates POST /resource response information based on different Magpie version formats.
    :param json_body: json body of the response to validate.
    :param resource_name: name of the resource to validate.
    :param resource_type: type of the resource to validate.
    :param resource_display_name: display name of the resource to validate.
    :param version: version of application/remote server to use for format validation, use local Magpie version if None.
    :raise failing condition
    """
    version = version or __meta__.__version__
    if LooseVersion(version) >= LooseVersion('0.6.3'):
        check_val_is_in('resource', json_body)
        check_val_type(json_body['resource'], dict)
        check_val_is_in('resource_name', json_body['resource'])
        check_val_is_in('resource_display_name', json_body['resource'])
        check_val_is_in('resource_type', json_body['resource'])
        check_val_is_in('resource_id', json_body['resource'])
        check_val_equal(json_body['resource']['resource_name'], resource_name)
        check_val_equal(json_body['resource']['resource_display_name'], resource_display_name)
        check_val_equal(json_body['resource']['resource_type'], resource_type)
        check_val_type(json_body['resource']['resource_id'], int)
    else:
        check_val_is_in('resource_name', json_body)
        check_val_is_in('resource_type', json_body)
        check_val_is_in('resource_id', json_body)
        check_val_equal(json_body['resource_name'], resource_name)
        check_val_equal(json_body['resource_type'], resource_type)
        check_val_type(json_body['resource_id'], int)


def check_resource_children(resource_dict, parent_resource_id, root_service_id):
    """
    Crawls through a resource-children tree to validate data field, types and corresponding values.
    :param resource_dict: top-level 'resources' dictionary possibly containing children resources.
    :param parent_resource_id: top-level resource/service id (int)
    :param root_service_id: top-level service id (int)
    :raise any invalid match on expected data field, type or value
    """
    check_val_type(resource_dict, dict)
    for resource_id in resource_dict:
        check_val_type(resource_id, six.string_types)
        resource_int_id = int(resource_id)  # should by an 'int' string, no error raised
        resource_info = resource_dict[resource_id]
        check_val_is_in('root_service_id', resource_info)
        check_val_type(resource_info['root_service_id'], int)
        check_val_equal(resource_info['root_service_id'], root_service_id)
        check_val_is_in('resource_id', resource_info)
        check_val_type(resource_info['resource_id'], int)
        check_val_equal(resource_info['resource_id'], resource_int_id)
        check_val_is_in('parent_id', resource_info)
        check_val_type(resource_info['parent_id'], int)
        check_val_equal(resource_info['parent_id'], parent_resource_id)
        check_val_is_in('resource_name', resource_info)
        check_val_type(resource_info['resource_name'], six.string_types)
        check_val_is_in('resource_display_name', resource_info)
        check_val_type(resource_info['resource_display_name'], six.string_types)
        check_val_is_in('permission_names', resource_info)
        check_val_type(resource_info['permission_names'], list)
        check_val_is_in('children', resource_info)
        check_resource_children(resource_info['children'], resource_int_id, root_service_id)


# Generic setup and validation methods across unittests
# noinspection PyPep8Naming
class TestSetup(object):
    @staticmethod
    def get_Version(test_class):
        resp = test_request(test_class.url, 'GET', '/version',
                            headers=test_class.json_headers, cookies=test_class.cookies)
        json_body = check_response_basic_info(resp, 200)
        return json_body['version']

    @staticmethod
    def check_UpStatus(test_class, method, path):
        """
        Verifies that the Magpie UI page at very least returned an Ok response with the displayed title.
        Validates that at the bare minimum, no underlying internal error occurred from the API or UI calls.
        """
        resp = test_request(test_class.url, method, path, cookies=test_class.cookies, timeout=20)
        check_val_equal(resp.status_code, 200)
        check_val_is_in('Content-Type', dict(resp.headers))
        check_val_is_in('text/html', get_response_content_types_list(resp))
        check_val_is_in("Magpie Administration", resp.text)

    @staticmethod
    def check_Unauthorized(test_class, method, path, content_type='application/json'):
        """
        Verifies that Magpie returned an Unauthorized response.
        Validates that at the bare minimum, no underlying internal error occurred from the API or UI calls.
        """
        resp = test_request(test_class.url, method, path, cookies=test_class.cookies, expect_errors=True)
        check_response_basic_info(resp, expected_code=401, expected_type=content_type, expected_method=method)

    @staticmethod
    def get_AnyServiceOfTestServiceType(test_class):
        route = '/services/types/{}'.format(test_class.test_service_type)
        resp = test_request(test_class.url, 'GET', route, headers=test_class.json_headers, cookies=test_class.cookies)
        json_body = check_response_basic_info(resp, 200, expected_method='GET')
        check_val_is_in('services', json_body)
        check_val_is_in(test_class.test_service_type, json_body['services'])
        check_val_not_equal(len(json_body['services'][test_class.test_service_type]), 0,
                            msg="Missing any required service of type: `{}`".format(test_class.test_service_type))
        services_dict = json_body['services'][test_class.test_service_type]
        return services_dict.values()[0]

    @staticmethod
    def create_TestServiceResource(test_class, data_override=None):
        TestSetup.create_TestService(test_class)
        route = '/services/{svc}/resources'.format(svc=test_class.test_service_name)
        data = {
            "resource_name": test_class.test_resource_name,
            "resource_type": test_class.test_resource_type,
        }
        if data_override:
            data.update(data_override)
        resp = test_request(test_class.url, 'POST', route,
                            headers=test_class.json_headers,
                            cookies=test_class.cookies, json=data)
        return check_response_basic_info(resp, 201, expected_method='POST')

    @staticmethod
    def get_ExistingTestServiceInfo(test_class):
        route = '/services/{svc}'.format(svc=test_class.test_service_name)
        resp = test_request(test_class.url, 'GET', route,
                            headers=test_class.json_headers, cookies=test_class.cookies)
        json_body = get_json_body(resp)
        return json_body[test_class.test_service_name]

    @staticmethod
    def get_TestServiceDirectResources(test_class, ignore_missing_service=False):
        route = '/services/{svc}/resources'.format(svc=test_class.test_service_name)
        resp = test_request(test_class.url, 'GET', route,
                            headers=test_class.json_headers, cookies=test_class.cookies,
                            expect_errors=ignore_missing_service)
        if ignore_missing_service and resp.status_code == 404:
            return []
        json_body = get_json_body(resp)
        resources = json_body[test_class.test_service_name]['resources']
        return [resources[res] for res in resources]

    @staticmethod
    def check_NonExistingTestServiceResource(test_class):
        resources = TestSetup.get_TestServiceDirectResources(test_class, ignore_missing_service=True)
        resources_names = [res['resource_name'] for res in resources]
        check_val_not_in(test_class.test_resource_name, resources_names)

    @staticmethod
    def delete_TestServiceResource(test_class, override_resource_name=None):
        resource_name = override_resource_name or test_class.test_resource_name
        resources = TestSetup.get_TestServiceDirectResources(test_class, ignore_missing_service=True)
        test_resource = filter(lambda r: r['resource_name'] == resource_name, resources)
        # delete as required, skip if non-existing
        if len(test_resource) > 0:
            resource_id = test_resource[0]['resource_id']
            route = '/services/{svc}/resources/{res_id}'.format(svc=test_class.test_service_name, res_id=resource_id)
            resp = test_request(test_class.url, 'DELETE', route,
                                headers=test_class.json_headers,
                                cookies=test_class.cookies)
            check_val_equal(resp.status_code, 200)
        TestSetup.check_NonExistingTestServiceResource(test_class)

    @staticmethod
    def create_TestService(test_class):
        data = {
            u'service_name': test_class.test_service_name,
            u'service_type': test_class.test_service_type,
            u'service_url': u'http://localhost:9000/{}'.format(test_class.test_service_name)
        }
        resp = test_request(test_class.url, 'POST', '/services', json=data,
                            headers=test_class.json_headers, cookies=test_class.cookies,
                            expect_errors=True)
        if resp.status_code == 409:
            resp = test_request(test_class.url, 'GET', '/services',
                                headers=test_class.json_headers,
                                cookies=test_class.cookies)
            return check_response_basic_info(resp, 200, expected_method='GET')
        return check_response_basic_info(resp, 201, expected_method='POST')

    @staticmethod
    def check_NonExistingTestService(test_class):
        services_info = TestSetup.get_RegisteredServicesList(test_class)
        services_names = [svc['service_name'] for svc in services_info]
        check_val_not_in(test_class.test_service_name, services_names)

    @staticmethod
    def delete_TestService(test_class, override_service_name=None):
        service_name = override_service_name or test_class.test_service_name
        services_info = TestSetup.get_RegisteredServicesList(test_class)
        test_service = filter(lambda r: r['service_name'] == service_name, services_info)
        # delete as required, skip if non-existing
        if len(test_service) > 0:
            route = '/services/{svc_name}'.format(svc_name=test_class.test_service_name)
            resp = test_request(test_class.url, 'DELETE', route,
                                headers=test_class.json_headers,
                                cookies=test_class.cookies)
            check_val_equal(resp.status_code, 200)
        TestSetup.check_NonExistingTestService(test_class)

    @staticmethod
    def get_RegisteredServicesList(test_class):
        resp = test_request(test_class.url, 'GET', '/services',
                            headers=test_class.json_headers,
                            cookies=test_class.cookies)
        json_body = check_response_basic_info(resp, 200, expected_method='GET')

        # prepare a flat list of registered services
        services_list = list()
        for svc_type in json_body['services']:
            services_of_type = json_body['services'][svc_type]
            services_list.extend(services_of_type.values())
        return services_list

    @staticmethod
    def get_RegisteredUsersList(test_class):
        resp = test_request(test_class.url, 'GET', '/users',
                            headers=test_class.json_headers,
                            cookies=test_class.cookies)
        json_body = check_response_basic_info(resp, 200, expected_method='GET')
        return json_body['user_names']

    @staticmethod
    def check_NonExistingTestUser(test_class):
        users = TestSetup.get_RegisteredUsersList(test_class)
        check_val_not_in(test_class.test_user_name, users)

    @staticmethod
    def create_TestUser(test_class):
        data = {
            "user_name": test_class.test_user_name,
            "email": '{}@mail.com'.format(test_class.test_user_name),
            "password": test_class.test_user_name,
            "group_name": test_class.test_user_group,
        }
        resp = test_request(test_class.url, 'POST', '/users',
                            headers=test_class.json_headers,
                            cookies=test_class.cookies, json=data)
        return check_response_basic_info(resp, 201, expected_method='POST')

    @staticmethod
    def delete_TestUser(test_class):
        users = TestSetup.get_RegisteredUsersList(test_class)
        # delete as required, skip if non-existing
        if test_class.test_user_name in users:
            route = '/users/{usr}'.format(usr=test_class.test_user_name)
            resp = test_request(test_class.url, 'DELETE', route,
                                headers=test_class.json_headers,
                                cookies=test_class.cookies)
            check_response_basic_info(resp, 200, expected_method='DELETE')
        TestSetup.check_NonExistingTestUser(test_class)

    @staticmethod
    def get_RegisteredGroupsList(test_class):
        resp = test_request(test_class.url, 'GET', '/groups',
                            headers=test_class.json_headers,
                            cookies=test_class.cookies)
        json_body = check_response_basic_info(resp, 200, expected_method='GET')
        return json_body['group_names']

    @staticmethod
    def check_NonExistingTestGroup(test_class):
        groups = TestSetup.get_RegisteredGroupsList(test_class)
        check_val_not_in(test_class.test_group_name, groups)

    @staticmethod
    def create_TestGroup(test_class):
        data = {"group_name": test_class.test_group_name}
        resp = test_request(test_class.url, 'POST', '/groups',
                            headers=test_class.json_headers,
                            cookies=test_class.cookies, json=data)
        return check_response_basic_info(resp, 201, expected_method='POST')

    @staticmethod
    def delete_TestGroup(test_class):
        groups = TestSetup.get_RegisteredGroupsList(test_class)
        # delete as required, skip if non-existing
        if test_class.test_group_name in groups:
            route = '/groups/{grp}'.format(grp=test_class.test_group_name)
            resp = test_request(test_class.url, 'DELETE', route,
                                headers=test_class.json_headers,
                                cookies=test_class.cookies)
            check_response_basic_info(resp, 200, expected_method='DELETE')
        TestSetup.check_NonExistingTestGroup(test_class)
