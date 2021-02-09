# Inspired by following extension but used locally as there are not pypi package.
# source: https://github.com/sphinx-contrib/redirects

import os

from sphinx.builders.html import StandaloneHTMLBuilder
from sphinx.builders.linkcheck import CheckExternalLinksBuilder
from sphinx.util import logging

LOGGER = logging.getLogger(__name__)

TEMPLATE = """<html>
  <head><meta http-equiv="refresh" content="0; url=%s"/></head>
</html>
"""


def generate_redirects(app):
    """
    This extension allows to fake a link to the HTML page actually generated by an RST file which contains a literal.

    *reference* to another RST file.

    For example, suppose we have two RST (ie: ``file1.rst`` and ``file2.rst`` ). Within ``file1.rst`` we got:

    .. code-block:: rst

        see `file2`_ details

        .. _file2: ./docs/file2.rst

    Normally, the generated HTML will have an hyperlink named ``file2`` with a *literal* reference to ``file2.rst``.
    This will result in HTTP Not Found (404) as it doesn't correspond to the generated ``file2.html``. Normally, this
    can be fixed using the following directive:

    .. code-block:: rst

        :doc:`./docs/file2.rst`

    But then, rendering on GitHub becomes literally this string with an hyperlink reference that doesn't lead to the
    desired ``file2.rst`` (for quick documentation locally within the GitHub repository).

    With this extension, if configuration is specified as follows, the HTML link is resolved by redirecting the literal
    ``./file2.rst`` reference in the output HTML build directory to the desired ``file2.html`` generated (as required).

    .. code-block:: python

        doc_redirect_map = {
            # mapping of: <actual-reference-in-rst> => <pointed-rst-generated-as-html>
            "file2.rst": "file2.rst"
        }

    In other words, when ``file1.rst`` is viewed from GitHub, the literal relative path is used an the file is found,
    while on ``Readthedocs`` (or when viewing locally in a browser), ``file1.html`` will contain a raw relative path to
    where the pointed ``file2.html`` *should* be using corresponding base directories. This is demonstrated below:

    .. code-block:: text

        '<root>/docs/file1.rst' ===> '<build-html>/file1.html' (ref [file2]) ---> (raw '<root>/docs/file2.rst')
                                                                                               |
                                                                                               |
        '<root>/docs/file2.rst' ===> '<build-html>/file2.html'   <------------------------------

    .. note::

        Literal RST file references must be relative to package root in other to be rendered correctly on GitHub.
    """

    if not isinstance(app.builder, (StandaloneHTMLBuilder, CheckExternalLinksBuilder)):
        ext = os.path.split(__file__)[-1].split(".")[0]
        builder = type(app.builder)
        LOGGER.warning("Extension '{}' is only supported by the 'html' builder [builder: {}]. ".format(ext, builder) +
                       "Skipping...")
        return
    if not isinstance(app.config.doc_redirect_map, dict) and len(app.config.doc_redirect_map):
        LOGGER.info("Could not find doc redirect map")
        return
    in_suffix = None
    if isinstance(app.config.source_suffix, list):
        in_suffix = app.config.source_suffix[0]
    elif isinstance(app.config.source_suffix, dict):
        in_suffix = list(app.config.source_suffix.items())[0][0]
    elif app.config.source_suffix:
        in_suffix = app.config.source_suffix
    if not in_suffix:
        in_suffix = ".rst"

    for from_path, to_path in app.config.doc_redirect_map.items():
        LOGGER.debug("Redirecting [%s] -> [%s]" % (from_path, to_path))

        rst_path = from_path
        if not rst_path.endswith(in_suffix):
            rst_path = rst_path + in_suffix
        html_path = from_path.replace(in_suffix, ".html")
        to_path_prefix = "..%s" % os.path.sep * (
            len(html_path.split(os.path.sep)) - 1)
        to_path = to_path_prefix + to_path.replace(in_suffix, ".html")
        if not to_path.endswith(".html"):
            to_path = to_path + ".html"
        LOGGER.debug("RST  [%s] -> [%s]" % (rst_path, to_path))
        LOGGER.debug("HTML [%s] -> [%s]" % (html_path, to_path))

        redirected_rst_file = os.path.join(app.builder.outdir, rst_path)
        redirected_html_file = os.path.join(app.builder.outdir, html_path)
        redirected_directory = os.path.dirname(redirected_html_file)
        if not os.path.exists(redirected_directory):
            os.makedirs(redirected_directory)

        # create unless it already exists (eg: same directory level, config map is redundant)
        if not os.path.exists(redirected_html_file):
            # if using a direct call with .html extension, it will still work as if calling the .rst
            with open(redirected_html_file, "w") as f:
                f.write(TEMPLATE % to_path)
        if not os.path.exists(redirected_rst_file):
            # point to the .rst that would be reach by clicking the literal reference
            # by faking an .html file redirect
            os.symlink(redirected_html_file, redirected_rst_file)


def setup(app):
    app.add_config_value("doc_redirect_map", {}, "env", dict)
    app.connect("builder-inited", generate_redirects)
