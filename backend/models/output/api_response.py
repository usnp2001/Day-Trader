from typing import Generic, TypeVar, Optional, Union
from pydantic import BaseModel
from http import HTTPStatus

T = TypeVar('T')

class ApiResponse(BaseModel, Generic[T]):
    status: int = 200
    message: str = "OK"
    result: Optional[T] = None

    @classmethod
    def create(cls, status: Union[int, HTTPStatus] = HTTPStatus.OK, message: Optional[str] = None, result: Optional[T] = None) -> "ApiResponse[T]":
        status_code = int(status)
        if message is None:
            try:
                message = HTTPStatus(status_code).phrase
            except ValueError:
                message = "OK" if status_code == 200 else "Error"
        return cls(status=status_code, message=message, result=result)

    def error_setting(self, status: Union[int, HTTPStatus], error_msg: str = ""):
        self.status = int(status)
        if error_msg:
            self.message = error_msg
        else:
            try:
                self.message = HTTPStatus(self.status).phrase
            except ValueError:
                self.message = "Error"

    def http_status_setting(self, status: Union[int, HTTPStatus], error_msg: str = "") -> int:
        self.status = int(status)
        if error_msg:
            self.message = error_msg
        else:
            try:
                self.message = HTTPStatus(self.status).phrase
            except ValueError:
                self.message = "Error"
        return 1
