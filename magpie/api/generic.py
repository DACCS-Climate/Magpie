from typing import TYPE_CHECKING

from pyramid.authentication import Authenticated
from pyramid.exceptions import PredicateMismatch
from pyramid.httpexceptions import (
    HTTPException,
    HTTPForbidden,
    HTTPInternalServerError,
    HTTPMethodNotAllowed,
    HTTPNotAcceptable,
    HTTPNotFound,
    HTTPServerError,
    HTTPUnauthorized
)
from pyramid.request import Request
from simplejson import JSONDecodeError

from magpie.api import exception as ax
from magpie.api import schemas as s
from magpie.api.requests import get_principals
from magpie.utils import (
    CONTENT_TYPE_ANY,
    CONTENT_TYPE_HTML,
    CONTENT_TYPE_JSON,
    FORMAT_TYPE_MAPPING,
    SUPPORTED_ACCEPT_TYPES,
    get_header,
    get_logger,
    is_magpie_ui_path,
)

if TYPE_CHECKING:
    # pylint: disable=W0611,unused-import
    from typing import Callable, Optional, Tuple, Union
    from magpie.typedefs import Str, JSON
    from pyramid.registry import Registry
    from pyramid.response import Response
LOGGER = get_logger(__name__)


def internal_server_error(request):
    # type: (Request) -> HTTPException
    """
    Overrides default HTTP.
    """
    content = get_request_info(request, exception_details=True,
                               default_message=s.InternalServerErrorResponseSchema.description)
    return ax.raise_http(nothrow=True, http_error=HTTPInternalServerError, detail=content["detail"], content=content)


def not_found_or_method_not_allowed(request):
    # type: (Request) -> HTTPException
    """
    Overrides the default ``HTTPNotFound`` [404] by appropriate ``HTTPMethodNotAllowed`` [405] when applicable.

    Not found response can correspond to underlying process operation not finding a required item, or a completely
    unknown route (path did not match any existing API definition).
    Method not allowed is more specific to the case where the path matches an existing API route, but the specific
    request method (GET, POST, etc.) is not allowed on this path.

    Without this fix, both situations return [404] regardless.
    """
    if (isinstance(request.exception, PredicateMismatch)
        and request.method not in request.exception._safe_methods   # pylint: disable=W0212  # noqa: W0212
    ):
        http_err = HTTPMethodNotAllowed
        http_msg = ""   # auto-generated by HTTPMethodNotAllowed
    else:
        http_err = HTTPNotFound
        http_msg = s.NotFoundResponseSchema.description
    content = get_request_info(request, default_message=http_msg)
    return ax.raise_http(nothrow=True, http_error=http_err, detail=content["detail"], content=content)


def unauthorized_or_forbidden(request):
    # type: (Request) -> HTTPException
    """
    Overrides the default ``HTTPForbidden`` [403] by appropriate ``HTTPUnauthorized`` [401] when applicable.

    Unauthorized response is for restricted user access according to missing credentials and/or authorization headers.
    Forbidden response is for operation refused by the underlying process operations or due to insufficient permissions.

    Without this fix, both situations return [403] regardless.

    .. seealso::
        - http://www.restapitutorial.com/httpstatuscodes.html

    In case the request references to `Magpie UI` route, it is redirected to
    :meth:`magpie.ui.home.HomeViews.error_view` for it to handle and display the error accordingly.
    """
    http_err = HTTPForbidden
    http_msg = s.HTTPForbiddenResponseSchema.description
    principals = get_principals(request)
    if Authenticated not in principals:
        http_err = HTTPUnauthorized
        http_msg = s.UnauthorizedResponseSchema.description
    content = get_request_info(request, default_message=http_msg)
    if is_magpie_ui_path(request):
        from magpie.ui.utils import request_api
        path = request.route_path("error").replace("/magpie", "")
        data = {"error_request": content, "error_code": http_err.code}
        return request_api(request, path, "POST", data)  # noqa
    return ax.raise_http(nothrow=True, http_error=http_err, detail=content["detail"], content=content)


def guess_target_format(request):
    # type: (Request) -> Tuple[Str, bool]
    """
    Guess the best applicable response ``Content-Type`` header according to request ``Accept`` header and ``format``
    query, or defaulting to :py:data:`CONTENT_TYPE_JSON`.

    :returns: tuple of matched MIME-type and where it was found (``True``: header, ``False``: query)
    """
    format = FORMAT_TYPE_MAPPING.get(request.params.get("format"))
    is_header = False
    if not format:
        is_header = True
        format = get_header("accept", request.headers, default=CONTENT_TYPE_JSON, split=";,")
        if format != CONTENT_TYPE_JSON:
            # because most browsers enforce some 'visual' list of accept header, revert to JSON if detected
            # explicit request set by other client (e.g.: using 'requests') will have full control over desired content
            user_agent = get_header("user-agent", request.headers)
            if user_agent and any(browser in user_agent for browser in ["Mozilla", "Chrome", "Safari"]):
                format = CONTENT_TYPE_JSON
    if not format or format == CONTENT_TYPE_ANY:
        is_header = True
        format = CONTENT_TYPE_JSON
    return format, is_header


def validate_accept_header_tween(handler, registry):    # noqa: F811
    # type: (Callable[[Request], Response], Registry) -> Callable[[Request], Response]
    """
    Tween that validates that the specified request ``Accept`` header or ``format`` query (if any) is a supported one
    by the application and for the given context.

    :raises HTTPNotAcceptable: if desired ``Content-Type`` is not supported.
    """
    def validate_format(request):
        # type: (Request) -> Response
        """
        Validates the specified request according to its ``Accept`` header or ``format`` query, ignoring UI related
        routes that require more content-types than the ones supported by the API for display purposes
        (styles, images, etc.).
        """
        if not is_magpie_ui_path(request):
            accept, _ = guess_target_format(request)
            http_msg = s.NotAcceptableResponseSchema.description
            content = get_request_info(request, default_message=http_msg)
            ax.verify_param(accept, is_in=True, param_compare=SUPPORTED_ACCEPT_TYPES,
                            param_name="Accept Header or Format Query",
                            http_error=HTTPNotAcceptable, msg_on_fail=http_msg,
                            content=content, content_type=CONTENT_TYPE_JSON)  # enforce type to avoid recursion
        return handler(request)
    return validate_format


def apply_response_format_tween(handler, registry):    # noqa: F811
    # type: (Callable[[Request], HTTPException], Registry) -> Callable[[Request], Response]
    """
    Tween that obtains the request ``Accept`` header or ``format`` query (if any) to generate the response with the
    desired ``Content-Type``. The target ``Content-Type`` is expected to have been validated by
    :func:`validate_accept_header_tween` beforehand to handle not-acceptable errors.

    The tween also ensures that additional request metadata extracted from :func:`get_request_info` is applied to
    the response body if not already provided by a previous operation.
    """
    def apply_format(request):
        # type: (Request) -> HTTPException
        """
        Validates the specified request according to its ``Accept`` header, ignoring UI related routes that request more
        content-types than the ones supported by the application for display purposes (styles, images etc.).
        Alternatively, if no ``Accept`` header is found, look for equivalent value provided via query parameter.
        """
        # all magpie API routes expected to either call 'valid_http' or 'raise_http' of 'magpie.api.exception' module
        # an HTTPException is always returned, and content is a JSON-like string
        format, is_header = guess_target_format(request)
        if not is_header:
            # NOTE:
            # enforce the accept header in case it was specified with format query, since some renderer implementations
            # will afterward erroneously overwrite the 'content-type' value that we enforce when converting the response
            # from the HTTPException. See:
            #   - https://github.com/Pylons/webob/issues/204
            #   - https://github.com/Pylons/webob/issues/238
            #   - https://github.com/Pylons/pyramid/issues/1344
            request.accept = format
        resp = handler(request)  # no exception when EXCVIEW tween is placed under this tween
        if is_magpie_ui_path(request):
            if not resp.content_type:
                resp.content_type = CONTENT_TYPE_HTML
            return resp
        # return routes already converted (valid_http/raise_http where not used, pyramid already generated response)
        if not isinstance(resp, HTTPException):
            return resp
        # forward any headers such as session cookies to be applied
        metadata = get_request_info(request)
        return ax.generate_response_http_format(type(resp), {"headers": resp.headers}, resp.text, format, metadata)
    return apply_format


def get_exception_info(response, content=None, exception_details=False):
    # type: (Union[HTTPException, Request, Response], Optional[JSON], bool) -> JSON
    """
    Obtains additional exception content details about the :paramref:`response` according to available information.
    """
    content = content or {}
    if hasattr(response, "exception"):
        # handle error raised simply by checking for "json" property in python 3 when body is invalid
        has_json = False
        try:
            has_json = hasattr(response.exception, "json")
        except JSONDecodeError:
            pass
        if has_json and isinstance(response.exception.json, dict):
            content.update(response.exception.json)
        elif isinstance(response.exception, HTTPServerError) and hasattr(response.exception, "message"):
            content.update({"exception": str(response.exception.message)})
        elif isinstance(response.exception, Exception) and exception_details:
            content.update({"exception": type(response.exception).__name__})
            # get 'request.exc_info' or 'sys.exc_info', whichever one is available
            LOGGER.error("Request exception.", exc_info=getattr(response, "exc_info", True))
        if not content.get("detail"):
            detail = response.exception
            content["detail"] = str(detail) if detail is not None else None
    elif hasattr(response, "matchdict"):
        if response.matchdict is not None and response.matchdict != "":
            content.update(response.matchdict)
    return content


def get_request_info(request, default_message=None, exception_details=False):
    # type: (Union[Request, HTTPException], Optional[Str], bool) -> JSON
    """
    Obtains additional content details about the :paramref:`request` according to available information.
    """
    content = {
        "route_name": str(request.upath_info),
        "request_url": str(request.url),
        "detail": default_message,
        "method": request.method
    }
    content.update(get_exception_info(request, content=content, exception_details=exception_details))
    return content
