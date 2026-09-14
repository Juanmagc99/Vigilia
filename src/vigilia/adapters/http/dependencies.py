from typing import Annotated

from fastapi import Depends, Request

from vigilia.bootstrap.composition import ApiApplication


def get_application(request: Request) -> ApiApplication:
    return request.app.state.vigilia


ApplicationDependency = Annotated[ApiApplication, Depends(get_application)]
