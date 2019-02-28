from magpie.common import islambda, isclass, JSON_TYPE, HTML_TYPE, PLAIN_TYPE, CONTENT_TYPES
from magpie.definitions.pyramid_definitions import (
    HTTPError,
    HTTPException,
    HTTPInternalServerError,
    HTTPNotAcceptable,
    HTTPSuccessful,
    HTTPRedirection,
    HTTPOk,
)
from typing import TYPE_CHECKING
from sys import exc_info
import json
import six
if TYPE_CHECKING:
    from magpie.definitions.typedefs import (  # noqa: F401
        Any, Str, Callable, List, Iterable, Optional, Tuple, Union, JsonBody, ParamKWArgs, PyramidResponse
    )

# control variables to avoid infinite recursion in case of
# major programming error to avoid application hanging
RAISE_RECURSIVE_SAFEGUARD_MAX = 5
RAISE_RECURSIVE_SAFEGUARD_COUNT = 0


# noinspection PyPep8Naming
def verify_param(
                 # --- verification values ---
                 param,                             # type: Any
                 paramCompare=None,                 # type: Optional[Union[Any, List[Any]]]
                 # --- output options on failure ---
                 paramName=None,                    # type: Optional[Str]
                 withParam=True,                    # type: Optional[bool]
                 httpError=HTTPNotAcceptable,       # type: Optional[HTTPError]
                 httpKWArgs=None,                   # type: Optional[ParamKWArgs]
                 msgOnFail="",                      # type: Optional[Str]
                 content=None,                      # type: Optional[JsonBody]
                 contentType=JSON_TYPE,             # type: Optional[Str]
                 # --- verification flags (method) ---
                 notNone=False,                     # type: Optional[bool]
                 notEmpty=False,                    # type: Optional[bool]
                 notIn=False,                       # type: Optional[bool]
                 notEqual=False,                    # type: Optional[bool]
                 isTrue=False,                      # type: Optional[bool]
                 isFalse=False,                     # type: Optional[bool]
                 isNone=False,                      # type: Optional[bool]
                 isEmpty=False,                     # type: Optional[bool]
                 isIn=False,                        # type: Optional[bool]
                 isEqual=False,                     # type: Optional[bool]
                 ofType=False,                      # type: Optional[bool]
                 ):                                 # type: (...) -> None
    """
    Evaluate various parameter combinations given the requested verification flags.
    Given a failing verification, directly raises the specified ``httpError``.
    Invalid usage exceptions generated by this verification process are treated as :class:`HTTPInternalServerError`.
    Exceptions are generated using the standard output method.

    :param param: parameter value to evaluate
    :param paramCompare:
        other value(s) to test `param` against, can be an iterable (single value resolved as iterable unless `None`)
        to test for `None` type, use `isNone`/`notNone` flags instead
    :param paramName: name of the tested parameter returned in response if specified for debugging purposes
    :param httpError: derived exception to raise on test failure (default: `HTTPNotAcceptable`)
    :param httpKWArgs: additional keyword arguments to pass to `httpError` if called in case of HTTP exception
    :param msgOnFail: message details to return in HTTP exception if flag condition failed
    :param content: json formatted additional content to provide in case of exception
    :param contentType: format in which to return the exception (one of `magpie.common.CONTENT_TYPES`)
    :param notNone: test that `param` is None type
    :param notEmpty: test that `param` is an empty string
    :param notIn: test that `param` does not exist in `paramCompare` values
    :param notEqual: test that `param` is not equal to `paramCompare` value
    :param isTrue: test that `param` is `True`
    :param isFalse: test that `param` is `False`
    :param isNone: test that `param` is None type
    :param isEmpty: test `param` for an empty string
    :param isIn: test that `param` exists in `paramCompare` values
    :param isEqual: test that `param` equals `paramCompare` value
    :param ofType: test that `param` is of same type as specified by `paramCompare` type
    :param withParam: on raise, adds values of `param`, `paramName` and `paramCompare` to json response if specified
    :raises `HTTPError`: if tests fail, specified exception is raised (default: `HTTPNotAcceptable`)
    :raises `HTTPInternalServerError`: for evaluation error
    :return: nothing if all tests passed
    """
    content = {} if content is None else content

    # precondition evaluation of input parameters
    try:
        if type(notNone) is not bool:
            raise TypeError("`notNone` is not a `bool`")
        if type(notEmpty) is not bool:
            raise TypeError("`notEmpty` is not a `bool`")
        if type(notIn) is not bool:
            raise TypeError("`notIn` is not a `bool`")
        if type(notEqual) is not bool:
            raise TypeError("`notEqual` is not a `bool`")
        if type(isTrue) is not bool:
            raise TypeError("`isTrue` is not a `bool`")
        if type(isFalse) is not bool:
            raise TypeError("`isFalse` is not a `bool`")
        if type(isNone) is not bool:
            raise TypeError("`isNone` is not a `bool`")
        if type(isEmpty) is not bool:
            raise TypeError("`isEmpty` is not a `bool`")
        if type(isIn) is not bool:
            raise TypeError("`isIn` is not a `bool`")
        if type(isEqual) is not bool:
            raise TypeError("`isEqual` is not a `bool`")
        if type(ofType) is not bool:
            raise TypeError("`ofType` is not a `bool`")
        if paramCompare is None and (isIn or notIn or isEqual or notEqual):
            raise TypeError("`paramCompare` cannot be `None` with specified test flags")
        if isEqual or notEqual:
            # allow 'different' string literals for comparison, otherwise types must match exactly
            if not (isinstance(param, six.string_types) and
                    isinstance(paramCompare, six.string_types)) and type(param) != type(paramCompare):
                raise TypeError("`paramCompare` cannot be of incompatible type with specified test flags")
        if not hasattr(paramCompare, '__iter__') and (isIn or notIn):
            paramCompare = [paramCompare]
        # error if none of the flags specified
        if not any([notNone, notEmpty, notIn, notEqual, isTrue, isFalse, isNone, isEmpty, isIn, isEqual, ofType]):
            raise ValueError("no comparison flag specified for verification")
    except Exception as e:
        content[u'traceback'] = repr(exc_info())
        content[u'exception'] = repr(e)
        raise_http(httpError=HTTPInternalServerError, httpKWArgs=httpKWArgs,
                   content=content, contentType=contentType,
                   detail="Error occurred during parameter verification")

    # evaluate requested parameter combinations
    fail_verify = False
    if notNone:
        fail_verify = fail_verify or (param is None)
    if isNone:
        fail_verify = fail_verify or (param is not None)
    if isTrue:
        fail_verify = fail_verify or (param is False)
    if isFalse:
        fail_verify = fail_verify or (param is True)
    if notEmpty:
        fail_verify = fail_verify or (param == "")
    if isEmpty:
        fail_verify = fail_verify or (param != "")
    if notIn:
        fail_verify = fail_verify or (param in paramCompare)
    if isIn:
        fail_verify = fail_verify or (param not in paramCompare)
    if notEqual:
        fail_verify = fail_verify or (param == paramCompare)
    if isEqual:
        fail_verify = fail_verify or (param != paramCompare)
    if ofType:
        fail_verify = fail_verify or (not isinstance(param, paramCompare))
    if fail_verify:
        if withParam:
            content[u'param'] = {u'value': str(param)}
            if paramName is not None:
                content[u'param'][u'name'] = str(paramName)
            if paramCompare is not None:
                content[u'param'][u'compare'] = str(paramCompare)
        raise_http(httpError, httpKWArgs=httpKWArgs, detail=msgOnFail, content=content, contentType=contentType)


# noinspection PyPep8Naming
def evaluate_call(call,                                 # type: Optional[Callable[[], Any]]
                  fallback=None,                        # type: Optional[Callable[[], None]]
                  httpError=HTTPInternalServerError,    # type: Optional[HTTPError]
                  httpKWArgs=None,                      # type: Optional[ParamKWArgs]
                  msgOnFail="",                         # type: Optional[Str]
                  content=None,                         # type: Optional[JsonBody]
                  contentType=JSON_TYPE                 # type: Optional[Str]
                  ):                                    # type: (...) -> Any
    """
    Evaluates the specified ``call`` with a wrapped HTTP exception handling.
    On failure, tries to call ``fallback`` if specified, and finally raises the specified ``httpError``.
    Any potential error generated by ``fallback`` or ``httpError`` themselves are treated as
    :class:`HTTPInternalServerError`.
    Exceptions are generated using the standard output method formatted based on the specified ``contentType``.

    Example:
        normal call::

            try:
                res = func(args)
            except Exception as e:
                fb_func()
                raise HTTPExcept(e.message)

        wrapped call::

            res = evaluate_call(lambda: func(args), fallback=lambda: fb_func(), httpError=HTTPExcept, msgOnFail="...")


    :param call: function to call, *MUST* be specified as `lambda: <function_call>`
    :param fallback: function to call (if any) when `call` failed, *MUST* be `lambda: <function_call>`
    :param httpError: alternative exception to raise on `call` failure
    :param httpKWArgs: additional keyword arguments to pass to `httpError` if called in case of HTTP exception
    :param msgOnFail: message details to return in HTTP exception if `call` failed
    :param content: json formatted additional content to provide in case of exception
    :param contentType: format in which to return the exception (one of `magpie.common.CONTENT_TYPES`)
    :raises httpError: on `call` failure
    :raises `HTTPInternalServerError`: on `fallback` failure
    :return: whichever return value `call` might have if no exception occurred
    """
    msgOnFail = repr(msgOnFail) if type(msgOnFail) is not str else msgOnFail
    if not islambda(call):
        raise_http(httpError=HTTPInternalServerError, httpKWArgs=httpKWArgs,
                   detail="Input `call` is not a lambda expression",
                   content={u'call': {u'detail': msgOnFail, u'content': repr(content)}},
                   contentType=contentType)

    # preemptively check fallback to avoid possible call exception without valid recovery
    if fallback is not None:
        if not islambda(fallback):
            raise_http(httpError=HTTPInternalServerError, httpKWArgs=httpKWArgs,
                       detail="Input `fallback`  is not a lambda expression, not attempting `call`",
                       content={u'call': {u'detail': msgOnFail, u'content': repr(content)}},
                       contentType=contentType)
    try:
        return call()
    except Exception as e:
        ce = repr(e)
    try:
        if fallback is not None:
            fallback()
    except Exception as e:
        fe = repr(e)
        raise_http(httpError=HTTPInternalServerError, httpKWArgs=httpKWArgs,
                   detail="Exception occurred during `fallback` called after failing `call` exception",
                   content={u'call': {u'exception': ce, u'detail': msgOnFail, u'content': repr(content)},
                            u'fallback': {u'exception': fe}},
                   contentType=contentType)
    raise_http(httpError, detail=msgOnFail, httpKWArgs=httpKWArgs,
               content={u'call': {u'exception': ce, u'content': repr(content)}},
               contentType=contentType)


# noinspection PyPep8Naming
def valid_http(httpSuccess=HTTPOk,      # type: Optional[HTTPSuccessful]
               httpKWArgs=None,         # type: Optional[ParamKWArgs]
               detail="",               # type: Optional[Str]
               content=None,            # type: Optional[JsonBody]
               contentType=JSON_TYPE,   # type: Optional[Str]
               ):                       # type: (...) -> HTTPException
    """
    Returns successful HTTP with standardized information formatted with content type.
    (see :function:`raise_http` for HTTP error calls)

    :param httpSuccess: any derived class from base `HTTPSuccessful` (default: `HTTPOk`)
    :param httpKWArgs: additional keyword arguments to pass to `httpSuccess` when called
    :param detail: additional message information (default: empty)
    :param content: json formatted content to include
    :param contentType: format in which to return the exception (one of `magpie.common.CONTENT_TYPES`)
    :return `HTTPSuccessful`: formatted successful with additional details and HTTP code
    """
    global RAISE_RECURSIVE_SAFEGUARD_COUNT

    content = dict() if content is None else content
    detail = repr(detail) if type(detail) is not str else detail
    contentType = JSON_TYPE if contentType == '*/*' else contentType
    httpCode, detail, content = validate_params(httpSuccess, [HTTPSuccessful, HTTPRedirection],
                                                detail, content, contentType)
    json_body = format_content_json_str(httpCode, detail, content, contentType)
    resp = generate_response_http_format(httpSuccess, httpKWArgs, json_body, outputType=contentType)
    RAISE_RECURSIVE_SAFEGUARD_COUNT = 0  # reset counter for future calls (don't accumulate for different requests)
    return resp


# noinspection PyPep8Naming
def raise_http(httpError=HTTPInternalServerError,   # type: Optional[HTTPError]
               httpKWArgs=None,                     # type: Optional[ParamKWArgs]
               detail="",                           # type: Optional[Str]
               content=None,                        # type: Optional[JsonBody]
               contentType=JSON_TYPE,               # type: Optional[Str]
               nothrow=False                        # type: Optional[bool]
               ):                                   # type: (...) -> Union[HTTPException, None]
    """
    Raises error HTTP with standardized information formatted with content type.

    The content contains the corresponding http error code, the provided message as detail and
    optional specified additional json content (kwarg dict).

    .. seealso::
        :func:`valid_http` for HTTP successful calls

    :param httpError: any derived class from base `HTTPError` (default: `HTTPInternalServerError`)
    :param httpKWArgs: additional keyword arguments to pass to `httpError` if called in case of HTTP exception
    :param detail: additional message information (default: empty)
    :param content: json formatted content to include
    :param contentType: format in which to return the exception (one of `magpie.common.CONTENT_TYPES`)
    :param nothrow: returns the error response instead of raising it automatically, but still handles execution errors
    :raises HTTPError: formatted raised exception with additional details and HTTP code
    :returns: HTTPError formatted exception with additional details and HTTP code only if `nothrow` is `True`
    """

    # fail-fast if recursion generates too many calls
    # this would happen only if a major programming error occurred within this function
    global RAISE_RECURSIVE_SAFEGUARD_MAX
    global RAISE_RECURSIVE_SAFEGUARD_COUNT
    RAISE_RECURSIVE_SAFEGUARD_COUNT = RAISE_RECURSIVE_SAFEGUARD_COUNT + 1
    if RAISE_RECURSIVE_SAFEGUARD_COUNT > RAISE_RECURSIVE_SAFEGUARD_MAX:
        raise HTTPInternalServerError(detail="Terminated. Too many recursions of `raise_http`")

    # try dumping content with json format, `HTTPInternalServerError` with caller info if fails.
    # content is added manually to avoid auto-format and suppression of fields by `HTTPException`
    contentType = JSON_TYPE if contentType == '*/*' else contentType
    httpCode, detail, content = validate_params(httpError, HTTPError, detail, content, contentType)
    json_body = format_content_json_str(httpError.code, detail, content, contentType)
    resp = generate_response_http_format(httpError, httpKWArgs, json_body, outputType=contentType)

    # reset counter for future calls (don't accumulate for different requests)
    # following raise is the last in the chain since it wasn't triggered by other functions
    RAISE_RECURSIVE_SAFEGUARD_COUNT = 0
    if nothrow:
        return resp
    raise resp


# noinspection PyPep8Naming
def validate_params(httpClass,      # type: HTTPException
                    httpBase,       # type: Union[HTTPException, Iterable[HTTPException]]
                    detail,         # type: Str
                    content,        # type: Union[JsonBody, None]
                    contentType,    # type: Str
                    ):              # type: (...) -> Tuple[int, Str, JsonBody]
    """
    Validates parameter types and formats required by :function:`valid_http` and :function:`raise_http`.

    :param httpClass: any derived class from base `HTTPException` to verify
    :param httpBase: any derived sub-class(es) from base `HTTPException` as minimum requirement for `httpClass`
        (ie: 2xx, 4xx, 5xx codes). Can be a single class of an iterable of possible requirements (any).
    :param detail: additional message information (default: empty)
    :param content: json formatted content to include
    :param contentType: format in which to return the exception (one of `magpie.common.CONTENT_TYPES`)
    :raise `HTTPInternalServerError`: if any parameter is of invalid expected format
    :returns httpCode, detail, content: parameters with corrected and validated format if applicable
    """
    # verify input arguments, raise `HTTPInternalServerError` with caller info if invalid
    # cannot be done within a try/except because it would always trigger with `raise_http`
    content = dict() if content is None else content
    detail = repr(detail) if not isinstance(detail, six.string_types) else detail
    caller = {u'content': content, u'type': contentType, u'detail': detail, u'code': 520}  # 'unknown' code error
    verify_param(isclass(httpClass), paramName='httpClass', isTrue=True,
                 httpError=HTTPInternalServerError, contentType=JSON_TYPE, content={u'caller': caller},
                 msgOnFail="Object specified is not a class, class derived from `HTTPException` is expected.")
    # if `httpClass` derives from `httpBase` (ex: `HTTPSuccessful` or `HTTPError`) it is of proper requested type
    # if it derives from `HTTPException`, it *could* be different than base (ex: 2xx instead of 4xx codes)
    # return 'unknown error' (520) if not of lowest level base `HTTPException`, otherwise use the available code
    httpBase = tuple(httpBase if hasattr(httpBase, '__iter__') else [httpBase])
    # noinspection PyUnresolvedReferences
    httpCode = httpClass.code if issubclass(httpClass, httpBase) else \
               httpClass.code if issubclass(httpClass, HTTPException) else 520  # noqa: F401
    caller[u'code'] = httpCode
    verify_param(issubclass(httpClass, httpBase), paramName='httpBase', isTrue=True,
                 httpError=HTTPInternalServerError, contentType=JSON_TYPE, content={u'caller': caller},
                 msgOnFail="Invalid `httpBase` derived class specified.")
    verify_param(contentType, paramName='contentType', paramCompare=CONTENT_TYPES, isIn=True,
                 httpError=HTTPInternalServerError, contentType=JSON_TYPE, content={u'caller': caller},
                 msgOnFail="Invalid `contentType` specified for exception output.")
    return httpCode, detail, content


# noinspection PyPep8Naming
def format_content_json_str(httpCode, detail, content, contentType):
    """
    Inserts the code, details, content and type within the body using json format.
    Includes also any other specified json formatted content in the body.
    Returns the whole json body as a single string for output.

    :raise `HTTPInternalServerError`: if parsing of the json content failed
    :returns: formatted json content as string with added HTTP code and details
    """
    json_body = {}
    try:
        content[u'code'] = httpCode
        content[u'detail'] = detail
        content[u'type'] = contentType
        json_body = json.dumps(content)
    except Exception as e:
        msg = "Dumping json content `" + str(content) + \
              "` resulted in exception `" + repr(e) + "`"
        raise_http(httpError=HTTPInternalServerError, detail=msg,
                   contentType=JSON_TYPE,
                   content={u'traceback': repr(exc_info()), u'exception': repr(e),
                            u'caller': {u'content': repr(content),   # raw string to avoid recursive json.dumps error
                                        u'detail': detail,
                                        u'code': httpCode,
                                        u'type': contentType}})
    return json_body


# noinspection PyPep8Naming
def generate_response_http_format(httpClass, httpKWArgs, jsonContent, outputType=PLAIN_TYPE):
    # type: (Union[HTTPException, PyramidResponse], ParamKWArgs, JsonBody, Optional[Str]) -> PyramidResponse
    """
    Formats the HTTP response output according to desired ``outputType`` using provided HTTP code and content.

    :param httpClass: `HTTPException` derived class to use for output (code, generic title/explanation, etc.)
    :param httpKWArgs: additional keyword arguments to pass to `httpClass` when called
    :param jsonContent: formatted json content providing additional details for the response cause
    :param outputType: one of `magpie.common.CONTENT_TYPES` (default: `magpie.common.PLAIN_TYPE`)
    :return: `httpClass` instance with requested information and output type if creation succeeds
    :raises: `HTTPInternalServerError` instance details about requested information and output type if creation fails
    """
    # content body is added manually to avoid auto-format and suppression of fields by `HTTPException`
    jsonContent = str(jsonContent) if not type(jsonContent) == str else jsonContent

    # adjust additional keyword arguments and try building the http response class with them
    httpKWArgs = dict() if httpKWArgs is None else httpKWArgs
    try:
        # directly output json
        if outputType == JSON_TYPE:
            json_type = '{}; charset=UTF-8'.format(JSON_TYPE)
            httpResponse = httpClass(body=jsonContent, content_type=json_type, **httpKWArgs)

        # otherwise json is contained within the html <body> section
        elif outputType == HTML_TYPE:
            # add preformat <pre> section to output as is within the <body> section
            htmlBody = httpClass.explanation + "<br><h2>Exception Details</h2>" + \
                       "<pre style='word-wrap: break-word; white-space: pre-wrap;'>" + \
                       jsonContent + "</pre>"
            httpResponse = httpClass(body_template=htmlBody, content_type=HTML_TYPE, **httpKWArgs)

        # default back to plain text
        else:
            httpResponse = httpClass(body=jsonContent, content_type=PLAIN_TYPE, **httpKWArgs)

        return httpResponse
    except Exception as e:
        raise_http(httpError=HTTPInternalServerError, detail="Failed to build HTTP response",
                   content={u'traceback': repr(exc_info()), u'exception': repr(e),
                            u'caller': {u'httpKWArgs': repr(httpKWArgs),
                                        u'httpClass': repr(httpClass),
                                        u'outputType': str(outputType)}})
