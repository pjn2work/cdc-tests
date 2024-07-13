import functools
from typing import Dict, List
from urllib.parse import urlencode

import requests
from testipy.helpers import prettify
from testipy.helpers.data_driven_testing import ExecutionToolbox, SafeTry
from testipy.helpers.handle_assertions import ExpectedError
from testipy.helpers.rest import handle_http_response
from testipy.reporter import ReportManager
from testipy.reporter.report_base import TestDetails

BASE_URL = "http://127.0.0.1:8080/"
HEADERS = {"Authorization": ""}


class Context:
    def __init__(self):
        self.vars: Dict[str, str | Dict | List] = {}

    def save(self, name: str, data) -> None:
        self.vars["current"] = data
        if name:
            self.vars[name] = data

    def get(self, name: str = None) -> str | Dict | List:
        if name is None:
            return ""

        if "." not in name:
            if name not in self.vars[name]:
                raise ValueError(f"Variable {name} not saved in context!")
            return self.vars[name]

        fields = name.split(".")
        current_vars = self.vars
        _path = []
        for field in fields:
            _path.append(field)

            if field.isdigit() and isinstance(current_vars, List):
                current_vars = current_vars[int(field)]
            else:
                if field not in current_vars:
                    raise ValueError(f"Variable {'.'.join(_path)} not saved in context!")
                current_vars = current_vars[field]

        return current_vars


def handle_api_calls(_func=None, *, http_method:str = "GET"):

    def decorator(func):
        @functools.wraps(func)
        def handler_wrapper(*args, **kwargs):
            usecase = kwargs["usecase"]
            usecase_name = kwargs["usecase_name"]
            rm = kwargs["rm"]
            context = kwargs["context"]
            current_test = kwargs["current_test"]
            _assertions = usecase.get("_assertions", [])

            url = BASE_URL + str(usecase.get("url", ''))
            url = url.replace("?", str(context.get(usecase.get("_get"))))
            furl = "?".join(filter(None, [url, urlencode(usecase.get("params", {}))]))

            try:
                response = func(*args, url=url, **kwargs)

                context.save(usecase.get("_save"), response)
                rm.test_info(current_test, f"{usecase_name} - {http_method} {furl} - received payload:\n{prettify(response, as_yaml=False)}")

                for _message, _assertion in _assertions:
                    exec_method = f"assert {_assertion}, '{_message}'"
                    exec(exec_method)

                return response
            except Exception as ex:
                _show_expected_payload_vs_received(rm, current_test, usecase, usecase_name, url, http_method, ex)
                raise

        return handler_wrapper

    if _func is None:
        return decorator    # under a class instance
    else:
        return decorator(_func)


class Toolbox(ExecutionToolbox):

    def __init__(self):
        self.context = Context()

    def execute(self, rm: ReportManager, current_test: TestDetails, exec_method, usecase: Dict, usecase_name: str, st: SafeTry):
        exec_method = f"self.{usecase['_exec_method_']}(rm=rm, current_test=current_test, usecase=usecase, usecase_name=usecase_name, st=st, context=self.context)"
        eval(exec_method)

    def clear_last_execution(self):
        handle_http_response.body = handle_http_response.raw = ""

    # --- Execution Methods --------------------------------------------------------------------------------------------

    def clear_bearer_token(self, rm: ReportManager, current_test: TestDetails, usecase: Dict, usecase_name: str, **kwargs):
        HEADERS["Authorization"] = ""
        rm.test_info(current_test, f"{usecase_name} - Authorization cleared")

    def api_post_token(self, rm: ReportManager, current_test: TestDetails, usecase: Dict, usecase_name: str, **kwargs):
        url = f"{BASE_URL}oauth/token"
        furl = "?".join(filter(None, [url, urlencode(usecase.get("params", {}))]))
        try:
            response = _post_as_dict(url, params=usecase["params"], **usecase.get("control", {}), expected_response=usecase.get("expected_response"))
            HEADERS["Authorization"] = "Bearer " + response["access_token"]
            rm.test_info(current_test, f"{usecase_name} - POST {furl} - received payload:\n" + prettify(response, as_yaml=False))
        except Exception as ex:
            HEADERS["Authorization"] = ""
            _show_expected_payload_vs_received(rm, current_test, usecase, usecase_name, url, "POST", ex)
            raise

    @handle_api_calls(http_method="POST")
    def api_post(self, usecase: Dict, url: str, **kwargs):
        return _post_as_dict(url, data=usecase.get("data"), params=usecase.get("params"), expected_response=usecase.get("expected_response"), **usecase.get("control", {}))

    @handle_api_calls(http_method="GET")
    def api_get(self, usecase: Dict, url: str, **kwargs):
        return _get_as_dict(url, params=usecase.get("params"), expected_response=usecase.get("expected_response"), **usecase.get("control", {}))

    @handle_api_calls(http_method="GET")
    def api_list(self, usecase: Dict, url: str, **kwargs):
        return _get_as_list(url, params=usecase.get("params"), expected_response=usecase.get("expected_response"), **usecase.get("control", {}))

    @handle_api_calls(http_method="GET")
    def api_get_str(self, usecase: Dict, url: str = "", **kwargs):
        return _get_as_str(url, params=usecase.get("params"), expected_response=usecase.get("expected_response"), **usecase.get("control", {}))

    @handle_api_calls(http_method="PUT")
    def api_put(self, usecase: Dict, url: str, **kwargs):
        return _put_as_dict(url, data=usecase.get("data"), params=usecase.get("params"), expected_response=usecase.get("expected_response"), **usecase.get("control", {}))


@handle_http_response(expected_type=list)
def _get_as_list(url: str = "", params: Dict = None, timeout: int = 5, expected_status_code: int = 200, ok: int = 200, expected_response=None) -> Dict:
    return requests.get(url,
                        params=params,
                        headers={
                            "accept": "application/json",
                            **HEADERS
                        },
                        timeout=timeout)


@handle_http_response(expected_type=dict)
def _get_as_dict(url: str = "", params: Dict = None, timeout: int = 5, expected_status_code: int = 200, ok: int = 200, expected_response=None) -> Dict:
    return requests.get(url,
                        params=params,
                        headers={
                            "accept": "application/json",
                            **HEADERS
                        },
                        timeout=timeout)


@handle_http_response(expected_type=dict)
def _post_as_dict(url: str = "", data: Dict = None, params: Dict = None, timeout: int = 5, expected_status_code: int = 200, ok: int = 200, expected_response=None) -> Dict:
    return requests.post(url, json=data,
                         params=params,
                         headers={
                             "Content-Type": "application/json; charset=utf-8",
                             "accept": "application/json",
                             **HEADERS},
                         timeout=timeout)


@handle_http_response(expected_type=dict)
def _put_as_dict(url: str = "", data: Dict = None, params: Dict = None, timeout: int = 5, expected_status_code: int = 200, ok: int = 200, expected_response=None) -> Dict:
    return requests.put(url, json=data,
                        params=params,
                        headers={
                            "Content-Type": "application/json; charset=utf-8",
                            "accept": "application/json",
                            **HEADERS},
                        timeout=timeout)

@handle_http_response(expected_type=str)
def _get_as_str(url: str = "", params: Dict = None, timeout: int = 5, expected_status_code: int = 200, ok: int = 200, expected_response=None) -> Dict:
    return requests.get(url,
                        params=params,
                        headers={
                            "accept": "text/html",
                            **HEADERS
                        },
                        timeout=timeout)


def _show_expected_payload_vs_received(rm: ReportManager, current_test: TestDetails, usecase: Dict, usecase_name: str, url: str, http_method: str, ex: Exception):
    text = "\n" + prettify(handle_http_response.body or handle_http_response.raw.text, as_yaml=False)
    rm.test_info(
        current_test,
        info=f"{usecase_name} - {http_method} {url} - received Error payload:{text}",
        level="DEBUG" if isinstance(ex, ExpectedError) else "ERROR"
    )
    if expected_response := usecase.get("expected_response"):
        rm.test_info(current_test,
                     info=f"{usecase_name} - expected payload:\n{prettify(expected_response, as_yaml=False)}",
                     level="DEBUG")
