"""Public validation errors retain field locations without echoing input."""
from fastapi.responses import JSONResponse
from fastapi.exception_handlers import http_exception_handler


async def http_error(request, error):
    response = await http_exception_handler(request, error)
    response.headers['Cache-Control'] = 'no-store'
    if error.status_code == 401:
        response.headers.setdefault('WWW-Authenticate', 'Bearer')
    return response


async def validation_error(request, error):
    # Pydantic's input and context can contain passwords, tokens, or raw bodies.
    details = [{key: item[key] for key in ("type", "loc", "msg") if key in item}
               for item in error.errors()]
    return JSONResponse(status_code=422, content={"detail": details},
                        headers={"Cache-Control": "no-store"})
