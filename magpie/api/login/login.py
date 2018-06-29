from authomatic.adapters import WebObAdapter
from authomatic.providers import oauth1, oauth2, openid
from authomatic import Authomatic, provider_id
from security import authomatic

from definitions.pyramid_definitions import *
from definitions.ziggurat_definitions import *
from magpie import *
from api.api_except import *
from api.api_requests import *
from api.api_rest_schemas import *
from api.management.user.user_utils import create_user
import requests


external_providers_config = {
    'openid': {
        'class_': openid.OpenID,    # OpenID provider dependent on the python-openid package.
    },
    'github': {
        'class_': oauth2.GitHub,
        'consumer_key': '##########',
        'consumer_secret': '##########',
        'id': provider_id(),
        'scope': oauth2.GitHub.user_info_scope,
        '_apis': {
            'Get your events': ('GET', 'https://api.github.com/users/{user.username}/events'),
            'Get your watched repos': ('GET', 'https://api.github.com/user/subscriptions'),
        },
    },
    'dkrz': {
    },
    'ipsl': {
    },
    'badc': {
    },
    'pcmdi': {
    },
    'smhi': {
    },
}

external_providers_authomatic = Authomatic(config=external_providers_config, secret=os.getenv('MAGPIE_SECRET'))
external_providers = external_providers_config.keys()
internal_providers = [u'ziggurat']
providers = internal_providers + external_providers


@view_config(route_name='signin_external', request_method='POST', permission=NO_PERMISSION_REQUIRED)
def sign_in_external(request):
    provider_name = get_value_multiformat_post_checked(request, 'provider_name')
    user_name = get_value_multiformat_post_checked(request, 'user_name')
    verify_param(provider_name, paramCompare=providers, isIn=True, httpError=HTTPNotAcceptable,
                 msgOnFail="Invalid: `provider_name` not found within available providers.",
                 content={u'provider_name': str(provider_name), u'providers': providers})
    if provider_name == 'openid':
        query_field = dict(id=user_name)
    elif provider_name == 'github':
        query_field = dict(login_field=user_name)
    else:
        query_field = dict(username=user_name)

    came_from = request.POST.get('came_from', '/')
    request.response.set_cookie('homepage_route', came_from)
    external_login_route = request.route_url('external_login', provider_name=provider_name, _query=query_field)

    return HTTPFound(location=external_login_route, headers=request.response.headers)


@view_config(route_name='signin', request_method='POST', permission=NO_PERMISSION_REQUIRED)
def sign_in(request):
    provider_name = get_value_multiformat_post_checked(request, 'provider_name')
    user_name = get_value_multiformat_post_checked(request, 'user_name')
    password = get_multiformat_post(request, 'password')   # no check since password is None for external login#

    verify_param(provider_name, paramCompare=providers, isIn=True, httpError=HTTPNotAcceptable,
                 msgOnFail="Invalid `provider_name` not found within available providers",
                 content={u'provider_name': str(provider_name), u'providers': providers})

    if provider_name in internal_providers:
        signin_internal_url = '{}/signin_internal'.format(request.application_url)
        signin_internal_data = {u'user_name': user_name, u'password': password}
        signin_response = requests.post(signin_internal_url, data=signin_internal_data, allow_redirects=True)

        if signin_response.status_code == HTTPOk.code:
            pyramid_response = Response(body=signin_response.content, headers=signin_response.headers)
            for cookie in signin_response.cookies:
                pyramid_response.set_cookie(name=cookie.name, value=cookie.value, overwrite=True)
            return pyramid_response
        raise_http(httpError=HTTPUnauthorized, detail="Login failure.")

    elif provider_name in external_providers:
        return evaluate_call(lambda: sign_in_external(request, {u'user_name': user_name,
                                                                u'password': password,
                                                                u'provider_name': provider_name}),
                             httpError=HTTPInternalServerError, content={u'provider': provider_name},
                             msgOnFail="Error occurred while signing in with external provider")


@view_config(context=ZigguratSignInSuccess, permission=NO_PERMISSION_REQUIRED)
def login_success_ziggurat(request):
    # headers contains login authorization cookie
    return valid_http(httpSuccess=HTTPOk, detail="Login successful.", httpKWArgs={'headers': request.context.headers})


def new_user_external(external_user_name, external_id, email, provider_name, db_session):
    """create new user with an External Identity"""
    local_user_name = external_user_name + '_' + provider_name
    local_user_name = local_user_name.replace(" ", '_')
    create_user(local_user_name, password=None, email=email, group_name=USER_GROUP, db_session=db_session)

    user = UserService.by_user_name(local_user_name, db_session=db_session)
    ex_identity = models.ExternalIdentity(external_user_name=external_user_name, external_id=external_id,
                                          local_user_id=user.id, provider_name=provider_name)
    evaluate_call(lambda: db_session.add(ex_identity), fallback=lambda: db_session.rollback(),
                  httpError=HTTPConflict, msgOnFail="Add external user refused by db",
                  content={u'provider_name': str(provider_name), u'local_user_name': str(local_user_name)})
    user.external_identities.append(ex_identity)
    return user


def login_success_external(request, external_user_name, external_id, email, provider_name):
    # find user by external_id = login_id
    # replace user from mongodb by user ziggurat and connect to externalId
    user = ExternalIdentityService.user_by_external_id_and_provider(external_id, provider_name, request.db)
    if user is None:
        # create new user with an External Identity
        user = new_user_external(external_user_name=external_user_name, external_id=external_id,
                                 email=email, provider_name=provider_name, db_session=request.db)
    # set a header to remember (set-cookie) -> this is the important line
    headers = remember(request, user.id)
    # If redirection given

    homepage_route = '/' if 'homepage_route' not in request.cookies else str(request.cookies['homepage_route'])

    return valid_http(httpSuccess=HTTPFound, detail="External login homepage route found",
                      content={u'homepage_route': homepage_route},
                      httpKWArgs={'location': homepage_route, 'headers': headers})


@view_config(context=ZigguratSignInBadAuth, permission=NO_PERMISSION_REQUIRED)
def login_failure(request, reason=None):
    httpError = HTTPUnauthorized
    if reason is None:
        httpError = HTTPNotAcceptable
        reason = 'Undefined `user_name`.'
        user_name = request.POST.get('user_name')
        if user_name is None:
            httpError = HTTPBadRequest
            reason = 'Could not retrieve `user_name`.'
        else:
            user_name_list = evaluate_call(lambda: [user.user_name for user in models.User.all(db_session=request.db)],
                                           fallback=lambda: request.db.rollback(),
                                           httpError=HTTPForbidden, msgOnFail="Could not verify `user_name`.")
            if user_name in user_name_list:
                httpError = HTTPUnauthorized
                reason = 'Incorrect password.'
    raise_http(httpError=httpError, detail="Login failure", content={u'reason': str(reason)})


@view_config(context=ZigguratSignOut, permission=NO_PERMISSION_REQUIRED)
def sign_out_ziggurat(request):
    return valid_http(httpSuccess=HTTPOk, detail="Sign out successful.", httpKWArgs={'headers': forget(request)})


@view_config(route_name='external_login', permission=NO_PERMISSION_REQUIRED)
def authomatic_login(request):
    #_authomatic = authomatic(request)
    open_id_provider_name = request.matchdict.get('provider_name')

    # Start the login procedure.

    response = Response()
    result = external_providers_authomatic.login(WebObAdapter(request, response), open_id_provider_name)
    #result = _authomatic.login(WebObAdapter(request, response), open_id_provider_name)

    if result:
        if result.error:
            # Login procedure finished with an error.
            return login_failure(request, reason=result.error.message)
        elif result.user:
            if not (result.user.name and result.user.id):
                result.user.update()
            # Hooray, we have the user!
            if result.provider.name in ['openid', 'dkrz', 'ipsl', 'smhi', 'badc', 'pcmdi']:
                # TODO: change login_id ... more infos ...
                return login_success_external(request,
                                              external_id=result.user.id,
                                              email=result.user.email,
                                              provider_name=result.provider.name,
                                              external_user_name=result.user.name)
            elif result.provider.name == 'github':
                # TODO: fix email ... get more infos ... which login_id?
                login_id = "{0.username}@github.com".format(result.user)
                # email = "{0.username}@github.com".format(result.user)
                # get extra info
                if result.user.credentials:
                    pass
                return login_success_external(request,
                                              external_id=login_id,
                                              email=login_id,
                                              provider_name=result.provider.name,
                                              external_user_name=result.user.name)

    return response


@SessionAPI.get(schema=Session_GET_ResponseBodySchema(), tags=[LoginTag], response_schemas={
    '200': Session_GET_OkResponseSchema(description="Get session successful."),
    '500': InternalServerErrorResponseSchema(description="Failed to get session details.")
})
@view_config(route_name='session', permission=NO_PERMISSION_REQUIRED)
def get_session(request):
    def _get_session(req):
        authn_policy = req.registry.queryUtility(IAuthenticationPolicy)
        principals = authn_policy.effective_principals(req)
        if Authenticated in principals:
            user = request.user
            json_resp = {u'authenticated': True,
                         u'user_name': user.user_name,
                         u'user_email': user.email,
                         u'group_names': [group.group_name for group in user.groups]}
        else:
            json_resp = {u'authenticated': False}
        return json_resp

    session_json = evaluate_call(lambda: _get_session(request), httpError=HTTPInternalServerError,
                                 msgOnFail="Failed to get session details.")
    return valid_http(httpSuccess=HTTPOk, detail="Get session successful.", content=session_json)


@view_config(route_name='providers', request_method='GET', permission=NO_PERMISSION_REQUIRED)
def get_providers(request):
    return valid_http(httpSuccess=HTTPOk, detail="Get providers successful",
                      content={u'provider_names': providers,
                               u'internal_providers': internal_providers,
                               u'external_providers': external_providers})
