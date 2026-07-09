from fastapi import HTTPException

class ServiceException(Exception):
    """Custom exception raised by services to indicate business logic failures."""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code

class ResourceNotFoundException(ServiceException):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, status_code=404)

class ValidationException(ServiceException):
    def __init__(self, message: str = "Validation failed"):
        super().__init__(message, status_code=400)

class AuthenticationException(ServiceException):
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, status_code=401)

class AuthorizationException(ServiceException):
    def __init__(self, message: str = "Permission denied"):
        super().__init__(message, status_code=403)
