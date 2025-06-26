from __future__ import annotations

import sys

if sys.version_info >= (3, 11):
    from http import HTTPMethod
else:
    from enum import Enum

    # vendoring from stdlib for compat with older versions of Python
    class HTTPMethod(str, Enum):
        """HTTP methods and descriptions

        Methods from the following RFCs are all observed:

            * RFC 9110: HTTP Semantics, obsoletes 7231, which obsoleted 2616
            * RFC 5789: PATCH Method for HTTP
        """

        def __new__(cls, value, description):
            obj = str.__new__(cls, value)
            obj._value_ = value
            obj.description = description
            return obj

        def __repr__(self):
            return "<%s.%s>" % (self.__class__.__name__, self._name_)

        CONNECT = "CONNECT", "Establish a connection to the server."
        DELETE = "DELETE", "Remove the target."
        GET = "GET", "Retrieve the target."
        HEAD = (
            "HEAD",
            "Same as GET, but only retrieve the status line and header section.",
        )
        OPTIONS = "OPTIONS", "Describe the communication options for the target."
        PATCH = "PATCH", "Apply partial modifications to a target."
        POST = "POST", "Perform target-specific processing with the request payload."
        PUT = "PUT", "Replace the target with the request payload."
        TRACE = (
            "TRACE",
            "Perform a message loop-back test along the path to the target.",
        )


__all__ = [
    "HTTPMethod",
]
