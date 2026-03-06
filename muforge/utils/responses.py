import typing

import pydantic
from fastapi.responses import StreamingResponse


async def json_array_generator(
    data: typing.AsyncGenerator[pydantic.BaseModel, None],
) -> typing.AsyncGenerator[str, None]:
    # Start the JSON array
    yield "["
    first = True
    # Stream the rows from the DB
    async for element in data:
        # Insert commas between elements
        if not first:
            yield ","
        else:
            first = False
        # Convert your Pydantic model to JSON. (Assumes CharacterModel has .json())
        yield element.model_dump_json()
    # End the JSON array
    yield "]"


def streaming_list(
    data: typing.AsyncGenerator[pydantic.BaseModel, None],
) -> StreamingResponse:
    return StreamingResponse(
        json_array_generator(data),
        media_type="application/json",
    )
