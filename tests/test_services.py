#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_services
----------------------------------

Tests for the services implementations magpie.
"""
import unittest
from typing import TYPE_CHECKING

import pytest
import six

from magpie import __meta__, owsrequest
from magpie.adapter.magpieowssecurity import OWSAccessForbidden
from magpie.constants import get_constant
from magpie.permissions import Access, Permission, PermissionSet, Scope
from magpie.services import ServiceAPI, ServiceWPS
from magpie.utils import CONTENT_TYPE_FORM, CONTENT_TYPE_JSON, CONTENT_TYPE_PLAIN
from tests import interfaces as ti, runner, utils

if TYPE_CHECKING:
    # pylint: disable=W0611,unused-import
    from typing import Dict, Optional

    from magpie.typedefs import Str


def make_ows_parser(method="GET", content_type=None, params=None, body=""):
    # type: (Str, Optional[Str], Optional[Dict[Str, Str]], Optional[Str]) -> owsrequest.OWSParser
    """
    Makes an :class:`owsrequest.OWSParser` from mocked request definition with provided parameters for testing.
    """
    request = utils.mock_request("", params=params, body=body, method=method, content_type=content_type)
    if params is None:
        parse_params = []
    else:
        parse_params = params.keys()

    parser = owsrequest.ows_parser_factory(request)
    parser.parse(parse_params)
    return parser


@runner.MAGPIE_TEST_LOCAL
@runner.MAGPIE_TEST_SERVICES
class TestOWSParser(unittest.TestCase):
    def test_ows_parser_factory(self):  # noqa: R0201
        parser = make_ows_parser(method="GET", content_type=None, params=None, body="")
        assert isinstance(parser, owsrequest.WPSGet)

        params = {"test": "something"}
        parser = make_ows_parser(method="GET", content_type=None, params=params, body="")
        assert isinstance(parser, owsrequest.WPSGet)
        assert parser.params["test"] == "something"

        body = six.ensure_binary('<?xml version="1.0" encoding="UTF-8"?><Execute/>')    # pylint: disable=C4001
        parser = make_ows_parser(method="POST", content_type=None, params=None, body=body)
        assert isinstance(parser, owsrequest.WPSPost)

        body = '{"test": "something"}'  # pylint: disable=C4001
        parser = make_ows_parser(method="POST", content_type=None, params=None, body=body)
        parser.parse(["test"])
        assert isinstance(parser, owsrequest.MultiFormatParser)
        assert parser.params["test"] == "something"

        body = '{"test": "something"}'  # pylint: disable=C4001
        parser = make_ows_parser(method="POST", content_type=CONTENT_TYPE_PLAIN, params=None, body=body)
        parser.parse(["test"])
        assert isinstance(parser, owsrequest.MultiFormatParser)
        assert parser.params["test"] == "something"

        params = {"test": "something"}
        parser = make_ows_parser(method="POST", content_type=CONTENT_TYPE_FORM, params=params, body="")
        parser.parse(["test"])
        assert isinstance(parser, owsrequest.MultiFormatParser)
        assert parser.params["test"] == "something"

        params = {"test": "something"}
        parser = make_ows_parser(method="DELETE", content_type=None, params=params, body="")
        parser.parse(["test"])
        assert isinstance(parser, owsrequest.WPSGet)
        assert parser.params["test"] == "something"

        params = {"test": "something"}
        parser = make_ows_parser(method="PATCH", content_type=None, params=params, body="")
        parser.parse(["test"])
        assert isinstance(parser, owsrequest.WPSGet)
        assert parser.params["test"] == "something"

        body = '{"test": "something"}'  # pylint: disable=C4001
        parser = make_ows_parser(method="PATCH", content_type=CONTENT_TYPE_JSON, params=None, body=body)
        parser.parse(["test"])
        assert isinstance(parser, owsrequest.MultiFormatParser)
        assert parser.params["test"] == "something"


@runner.MAGPIE_TEST_LOCAL
@runner.MAGPIE_TEST_SERVICES
@runner.MAGPIE_TEST_FUNCTIONAL
class TestServices(ti.SetupMagpieAdapter, ti.AdminTestCase, ti.BaseTestCase):
    __test__ = True

    @classmethod
    @utils.mock_get_settings
    def setUpClass(cls):
        cls.version = __meta__.__version__
        cls.app = utils.get_test_magpie_app(cls.settings)
        cls.grp = get_constant("MAGPIE_ADMIN_GROUP")
        cls.usr = get_constant("MAGPIE_TEST_ADMIN_USERNAME")
        cls.pwd = get_constant("MAGPIE_TEST_ADMIN_PASSWORD")
        cls.settings = cls.app.app.registry.settings
        ti.SetupMagpieAdapter.setup(cls.settings)

        cls.cookies = None
        cls.version = utils.TestSetup.get_Version(cls)
        cls.setup_admin()
        cls.headers, cls.cookies = utils.check_or_try_login_user(cls.app, cls.usr, cls.pwd, use_ui_form_submit=True)
        cls.require = "cannot run tests without logged in user with '{}' permissions".format(cls.grp)
        cls.check_requirements()

        # following will be wiped on setup
        cls.test_user_name = "unittest-service-user"
        cls.test_group_name = "unittest-service-group"

    def mock_request(self, *args, **kwargs):
        kwargs.update({"cookies": self.test_cookies, "headers": self.test_headers})
        return super(TestServices, self).mock_request(*args, **kwargs)

    @utils.mock_get_settings
    def test_ServiceAPI_effective_permissions(self):
        """
        Evaluates functionality of :class:`ServiceAPI` against a mocked `Magpie` adapter for `Twitcher`.

        Legend::

            r: read     (HTTP HEAD/GET for ServiceAPI)
            w: write    (all other HTTP methods)
            A: allow
            D: deny
            M: match
            R: recursive

        Permissions Applied::
                                        user            group           effective (reason/importance)
            Service1                    (w-D-M)         (w-A-R)         r-D, w-D  (user > group)
                Resource1               (r-A-R)                         r-A, w-A
                    Resource2                           (r-D-R)         r-D, w-A  (revert user-res1)
                        Resource3       (w-A-R)         (w-D-M)         r-D, w-A  (user > group)
                            Resource4                   (w-D-M)         r-D, w-D  (match > recursive)
        """
        utils.TestSetup.create_TestGroup(self)
        utils.TestSetup.create_TestUser(self)

        svc_name = "unittest-service-api"
        svc_type = ServiceAPI.service_type
        res_type = ServiceAPI.resource_types[0].resource_type_name
        res_name = "sub"
        res_kw = {"override_resource_name": res_name, "override_resource_type": res_type}
        utils.TestSetup.delete_TestService(self, override_service_name=svc_name)
        body = utils.TestSetup.create_TestService(self, override_service_name=svc_name, override_service_type=svc_type)
        info = utils.TestSetup.get_ResourceInfo(self, override_body=body)
        svc_id = info["resource_id"]
        body = utils.TestSetup.create_TestResource(self, parent_resource_id=svc_id, **res_kw)
        info = utils.TestSetup.get_ResourceInfo(self, override_body=body)
        res1_id = info["resource_id"]
        body = utils.TestSetup.create_TestResource(self, parent_resource_id=res1_id, **res_kw)
        info = utils.TestSetup.get_ResourceInfo(self, override_body=body)
        res2_id = info["resource_id"]
        body = utils.TestSetup.create_TestResource(self, parent_resource_id=res2_id, **res_kw)
        info = utils.TestSetup.get_ResourceInfo(self, override_body=body)
        res3_id = info["resource_id"]
        body = utils.TestSetup.create_TestResource(self, parent_resource_id=res3_id, **res_kw)
        info = utils.TestSetup.get_ResourceInfo(self, override_body=body)
        res4_id = info["resource_id"]

        # setup permissions
        rAR = PermissionSet(Permission.READ, Access.ALLOW, Scope.RECURSIVE)     # noqa
        rDR = PermissionSet(Permission.READ, Access.DENY, Scope.RECURSIVE)      # noqa
        wAR = PermissionSet(Permission.WRITE, Access.ALLOW, Scope.RECURSIVE)    # noqa
        wDM = PermissionSet(Permission.WRITE, Access.DENY, Scope.MATCH)         # noqa
        utils.TestSetup.create_TestUserResourcePermission(self, override_resource_id=svc_id, override_permission=wDM)
        utils.TestSetup.create_TestGroupResourcePermission(self, override_resource_id=svc_id, override_permission=wAR)
        utils.TestSetup.create_TestUserResourcePermission(self, override_resource_id=res1_id, override_permission=rAR)
        utils.TestSetup.create_TestGroupResourcePermission(self, override_resource_id=res2_id, override_permission=rDR)
        utils.TestSetup.create_TestUserResourcePermission(self, override_resource_id=res3_id, override_permission=wAR)
        utils.TestSetup.create_TestGroupResourcePermission(self, override_resource_id=res3_id, override_permission=wDM)
        utils.TestSetup.create_TestGroupResourcePermission(self, override_resource_id=res4_id, override_permission=wDM)

        # login test user for which the permissions were set
        utils.check_or_try_logout_user(self)
        cred = utils.check_or_try_login_user(self, username=self.test_user_name, password=self.test_user_name)
        self.test_headers, self.test_cookies = cred

        # Service1 direct call
        path = "/ows/proxy/{}".format(svc_name)
        req = self.mock_request(path, method="GET")
        utils.check_raises(lambda: self.ows.check_request(req), OWSAccessForbidden)
        req = self.mock_request(path, method="POST")
        utils.check_raises(lambda: self.ows.check_request(req), OWSAccessForbidden)

        # Service1/Resource1
        path = "/ows/proxy/{}/{}".format(svc_name, res_name)
        req = self.mock_request(path, method="GET")
        utils.check_no_raise(lambda: self.ows.check_request(req))
        req = self.mock_request(path, method="POST")
        utils.check_no_raise(lambda: self.ows.check_request(req))

        # Service1/Resource1/Resource2
        path = "/ows/proxy/{}/{}/{}".format(svc_name, res_name, res_name)
        req = self.mock_request(path, method="GET")
        utils.check_raises(lambda: self.ows.check_request(req), OWSAccessForbidden)
        req = self.mock_request(path, method="POST")
        utils.check_no_raise(lambda: self.ows.check_request(req))

        # Service1/Resource1/Resource2/Resource3
        path = "/ows/proxy/{}/{}/{}/{}".format(svc_name, res_name, res_name, res_name)
        req = self.mock_request(path, method="GET")
        utils.check_raises(lambda: self.ows.check_request(req), OWSAccessForbidden)
        req = self.mock_request(path, method="POST")
        utils.check_no_raise(lambda: self.ows.check_request(req))

        # Service1/Resource1/Resource2/Resource3/Resource4
        path = "/ows/proxy/{}/{}/{}/{}/{}".format(svc_name, res_name, res_name, res_name, res_name)
        req = self.mock_request(path, method="GET")
        utils.check_raises(lambda: self.ows.check_request(req), OWSAccessForbidden)
        req = self.mock_request(path, method="POST")
        utils.check_raises(lambda: self.ows.check_request(req), OWSAccessForbidden)

        # login with admin user, validate full access granted even if no explicit permissions was set admins
        utils.check_or_try_logout_user(self)
        cred = utils.check_or_try_login_user(self, username=self.usr, password=self.pwd)
        self.test_headers, self.test_cookies = cred
        for res_count in range(0, 5):
            path = "/ows/proxy/{}".format(svc_name) + res_count * "/{}".format(res_name)
            for method in ["GET", "POST", "PUT", "DELETE"]:
                req = self.mock_request(path, method=method)
                utils.check_no_raise(lambda: self.ows.check_request(req))

    @unittest.skip("impl")
    @pytest.mark.skip
    def test_ServiceTHREDDS_effective_permissions(self):
        """
        Evaluates functionality of :class:`ServiceTHREDDS` against a mocked `Magpie` adapter for `Twitcher`.
        """
        raise NotImplementedError  # FIXME

    @unittest.skip("impl")
    @pytest.mark.skip
    def test_ServiceNCWMS2_effective_permissions(self):
        """
        Evaluates functionality of :class:`ServiceNCWMS2` against a mocked `Magpie` adapter for `Twitcher`.
        """
        raise NotImplementedError  # FIXME

    @unittest.skip("impl")
    @pytest.mark.skip
    def test_ServiceGeoserverWMS_effective_permissions(self):
        """
        Evaluates functionality of :class:`ServiceGeoserverWMS` against a mocked `Magpie` adapter for `Twitcher`.
        """
        raise NotImplementedError  # FIXME

    @unittest.skip("impl")
    @pytest.mark.skip
    def test_ServiceWFS_effective_permissions(self):
        """
        Evaluates functionality of :class:`ServiceWFS` against a mocked `Magpie` adapter for `Twitcher`.
        """
        raise NotImplementedError  # FIXME

    @utils.mock_get_settings
    def test_ServiceWPS_effective_permissions(self):
        """
        Evaluates functionality of :class:`ServiceWFS` against a mocked `Magpie` adapter for `Twitcher`.

        Legend::

            g: GetCapabilities (*)
            d: DescribeProcess
            e: Execute
            A: allow
            D: deny
            M: match
            R: recursive

        Permissions Applied::
                                        user        group               effective
            Service1                    (g-A-R)                         g-A,    d-D, e-D
                Process1                (e-A-M)     (d-A-M)             g-A,    d-A, e-A
            Service2                    (d-A-R)     (g-A-R)             g-A,    d-A, e-D
                Process2                            (g-D-M), (e-A-M)    g-A(*), d-A, e-A
                Process3                (e-D-M)                         g-A,    d-A, e-D

        .. note:: (*)
            All ``GetCapabilities`` requests completely ignore ``identifier`` query parameter by resolving immediately
            to the parent WPS Service since no Process applies in this case.

            For this reason, although ``(g-D-M)`` is applied on ``Process2``, Process ``identifier`` does not take place
            in ``GetCapabilities``. Therefore, the ACL is immediately resolved with the parent ``Service2`` permission
            of ``(g-A-R)`` which grants effective access.
        """
        utils.TestSetup.create_TestGroup(self)
        utils.TestSetup.create_TestUser(self)

        # create services
        wps1_name = "unittest-service-wps-1"
        wps2_name = "unittest-service-wps-2"
        svc_type = ServiceWPS.service_type
        proc_type = ServiceWPS.resource_types[0].resource_type_name
        body = utils.TestSetup.create_TestService(self, override_service_name=wps1_name, override_service_type=svc_type)
        info = utils.TestSetup.get_ResourceInfo(self, override_body=body)
        wps1_id = info["resource_id"]
        body = utils.TestSetup.create_TestService(self, override_service_name=wps2_name, override_service_type=svc_type)
        info = utils.TestSetup.get_ResourceInfo(self, override_body=body)
        wps2_id = info["resource_id"]

        # create processes
        proc1_name = "unittest-process-1"
        body = utils.TestSetup.create_TestResource(self, parent_resource_id=wps1_id,
                                                   override_resource_name=proc1_name,
                                                   override_resource_type=proc_type)
        info = utils.TestSetup.get_ResourceInfo(self, override_body=body)
        proc1_id = info["resource_id"]
        proc2_name = "unittest-process-2"
        body = utils.TestSetup.create_TestResource(self, parent_resource_id=wps2_id,
                                                   override_resource_name=proc2_name,
                                                   override_resource_type=proc_type)
        info = utils.TestSetup.get_ResourceInfo(self, override_body=body)
        proc2_id = info["resource_id"]
        proc3_name = "unittest-process-3"
        body = utils.TestSetup.create_TestResource(self, parent_resource_id=wps2_id,
                                                   override_resource_name=proc3_name,
                                                   override_resource_type=proc_type)
        info = utils.TestSetup.get_ResourceInfo(self, override_body=body)
        proc3_id = info["resource_id"]

        # assign permissions
        gAR = PermissionSet(Permission.GET_CAPABILITIES, Access.ALLOW, Scope.RECURSIVE)     # noqa
        dAM = PermissionSet(Permission.DESCRIBE_PROCESS, Access.ALLOW, Scope.MATCH)         # noqa
        dAR = PermissionSet(Permission.DESCRIBE_PROCESS, Access.ALLOW, Scope.RECURSIVE)     # noqa
        eAM = PermissionSet(Permission.EXECUTE, Access.ALLOW, Scope.MATCH)                  # noqa
        eDM = PermissionSet(Permission.EXECUTE, Access.DENY, Scope.MATCH)                   # noqa
        utils.TestSetup.create_TestUserResourcePermission(self, override_resource_id=wps1_id, override_permission=gAR)
        utils.TestSetup.create_TestUserResourcePermission(self, override_resource_id=proc1_id, override_permission=eAM)
        utils.TestSetup.create_TestGroupResourcePermission(self, override_resource_id=proc1_id, override_permission=dAM)
        utils.TestSetup.create_TestUserResourcePermission(self, override_resource_id=wps2_id, override_permission=dAR)
        utils.TestSetup.create_TestGroupResourcePermission(self, override_resource_id=wps2_id, override_permission=gAR)
        utils.TestSetup.create_TestGroupResourcePermission(self, override_resource_id=proc2_id, override_permission=eAM)
        utils.TestSetup.create_TestUserResourcePermission(self, override_resource_id=proc3_id, override_permission=eDM)

        # login test user for which the permissions were set
        utils.check_or_try_logout_user(self)
        cred = utils.check_or_try_login_user(self, username=self.test_user_name, password=self.test_user_name)
        self.test_headers, self.test_cookies = cred

        # note:
        #   Following requests use various 'service' and 'request' values that do not necessarily match the exact format
        #   of corresponding enums to validate the request query parameters are parsed correctly with combinations that
        #   are actually handled by the real WPS service.

        # Service1 calls
        path = "/ows/proxy/{}".format(wps1_name)
        params = {"service": "WPS", "request": "GetCapabilities"}
        req = self.mock_request(path, method="GET", params=params)
        utils.check_no_raise(lambda: self.ows.check_request(req))
        params = {"service": "WPS", "request": "DescribeProcess"}
        req = self.mock_request(path, method="GET", params=params)
        utils.check_raises(lambda: self.ows.check_request(req), OWSAccessForbidden)
        params = {"service": "WPS", "request": "EXECUTE"}
        req = self.mock_request(path, method="GET", params=params)
        utils.check_raises(lambda: self.ows.check_request(req), OWSAccessForbidden)

        # Process1 calls
        path = "/ows/proxy/{}".format(wps1_name)
        params = {"service": "WPS", "request": "GetCapabilities", "identifier": proc1_name}  # see docstring notes
        req = self.mock_request(path, method="GET", params=params)
        utils.check_no_raise(lambda: self.ows.check_request(req))
        params = {"service": "WPS", "request": "DescribeProcess", "identifier": proc1_name}
        req = self.mock_request(path, method="GET", params=params)
        utils.check_no_raise(lambda: self.ows.check_request(req))
        params = {"service": "WPS", "request": "EXECUTE", "identifier": proc1_name}
        req = self.mock_request(path, method="GET", params=params)
        utils.check_no_raise(lambda: self.ows.check_request(req))

        # Service2 calls
        path = "/ows/proxy/{}".format(wps2_name)
        params = {"service": "WPS", "request": "GetCapabilities"}
        req = self.mock_request(path, method="GET", params=params)
        utils.check_no_raise(lambda: self.ows.check_request(req))
        params = {"service": "WPS", "request": "DescribeProcess"}
        req = self.mock_request(path, method="GET", params=params)
        utils.check_no_raise(lambda: self.ows.check_request(req))
        params = {"service": "WPS", "request": "EXECUTE"}
        req = self.mock_request(path, method="GET", params=params)
        utils.check_raises(lambda: self.ows.check_request(req), OWSAccessForbidden)

        # Process2 calls
        path = "/ows/proxy/{}".format(wps2_name)
        params = {"service": "WPS", "request": "GETCAPABILITIES", "identifier": proc2_name}  # see docstring notes
        req = self.mock_request(path, method="GET", params=params)
        utils.check_no_raise(lambda: self.ows.check_request(req))
        params = {"service": "WPS", "request": "DescribeProcess", "identifier": proc2_name}
        req = self.mock_request(path, method="GET", params=params)
        utils.check_no_raise(lambda: self.ows.check_request(req))
        params = {"service": "WPS", "request": "EXECUTE", "identifier": proc2_name}
        req = self.mock_request(path, method="GET", params=params)
        utils.check_no_raise(lambda: self.ows.check_request(req))

        # Process3 calls
        path = "/ows/proxy/{}".format(wps2_name)
        params = {"service": "WPS", "request": "GETCAPABILITIES", "identifier": proc3_name}  # see docstring notes
        req = self.mock_request(path, method="GET", params=params)
        utils.check_no_raise(lambda: self.ows.check_request(req))
        params = {"service": "WPS", "request": "DescribeProcess", "identifier": proc3_name}
        req = self.mock_request(path, method="GET", params=params)
        utils.check_no_raise(lambda: self.ows.check_request(req))
        params = {"service": "WPS", "request": "EXECUTE", "identifier": proc3_name}
        req = self.mock_request(path, method="GET", params=params)
        utils.check_raises(lambda: self.ows.check_request(req), OWSAccessForbidden)

    @unittest.skip("impl")
    @pytest.mark.skip
    def test_ServiceAccess_effective_permissions(self):
        """
        Evaluates functionality of :class:`ServiceAccess` against a mocked `Magpie` adapter for `Twitcher`.
        """
        raise NotImplementedError  # FIXME

    @unittest.skip("impl")
    @pytest.mark.skip
    def test_ServiceADES_effective_permissions(self):
        """
        Evaluates functionality of :class:`ServiceADES` against a mocked `Magpie` adapter for `Twitcher`.

        .. note::
            Service of type :class:`ServiceADES` is a combination of :class:`ServiceAPI` and :class:`ServiceWPS` with
            corresponding resources accessed through different endpoints and formats.
        """
        raise NotImplementedError  # FIXME: see https://github.com/Ouranosinc/Magpie/issues/360
