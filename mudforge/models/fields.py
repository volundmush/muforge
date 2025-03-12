from typing import Annotated, Optional
from pydantic import AfterValidator, constr

from mudforge import validators

name_line = constr(strip_whitespace=True, min_length=1, max_length=255)
optional_name_line = Optional[name_line]
rich_text = Annotated[str, AfterValidator(validators.rich_text)]
optional_rich_text = Annotated[Optional[str], AfterValidator(validators.optional_rich_text)]