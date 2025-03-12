import typing
import lark
import pydantic
import mudforge
from dataclasses import dataclass
from lark.exceptions import LarkError
from fastapi import HTTPException, status

PARSER_CACHE = dict()


@dataclass(slots=True)
class LockArguments:
    """
    A dataclass that's passed into lockfunc calls.

    The object is the thing being accessed.
    The subject is the user/character trying to access it.

    The access_type represents the kind of access, like "read" or "post".

    The args are the arguments passed to the lock function.
    """

    object: typing.Any
    subject: "ActingAs"
    access_type: str
    args: typing.List[str | int]


def _validate_lock_funcs(self, lock: lark.Tree):
        """
        Given a lark tree, validate all of the lock_funcs in the tree.
        If any don't exist, raise an HTTP_400_BAD_REQUEST.
        """
        for node in lock.iter_subtrees():
            if node.data == "function_call":
                func_name = node.children[0].value
                if func_name not in mudforge.LOCKFUNCS:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Unknown lock function: {func_name}",
                    )


def validate_lock(access_type: str, lock: str):
    if lock in PARSER_CACHE:
        return PARSER_CACHE[lock]
    try:
        parsed = mudforge.LOCKPARSER.parse(lock)
        _validate_lock_funcs(parsed)
        PARSER_CACHE[lock] = parsed
        return parsed
    except LarkError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid lock syntax for access_type {access_type}: {e}",
        )
    


def validate_all_locks(valid_locks: dict[str, str]) -> dict[str, str]:
    out = dict()
    for access_type, lock in valid_locks.items():
        access = access_type.strip().lower()
        if not access:
            raise ValueError("Access type cannot be empty or whitespace.")
        if not lock:
            raise ValueError(f"Lock for access_type {access} cannot be empty.")
        if " " in access:
            raise ValueError(f"Access type {access} cannot contain spaces.")
        try:
            validate_lock(access, lock)
        except HTTPException as e:
            raise ValueError(f"Invalid lock for access_type {access}: {e}")
        out[access] = lock
    return out


def optional_validate_locks(lock_data: dict[str, str] | None):
    if lock_data is None:
        return
    return validate_all_locks(lock_data)

class OptionalLocks(pydantic.BaseModel):
    locks: typing.Annotated[typing.Optional[dict[str, str]], pydantic.BeforeValidator(optional_validate_locks)] = None

class HasLocks(pydantic.BaseModel):
    """
    This is the base lockhandler used for generic lock checks. It should be specialized for
    different types of lock-holders or users if needed.

    That entity will then be the LockArguments.object that's passed into a lockfunc.
    """
    locks: typing.Annotated[dict[str, str], pydantic.AfterValidator(validate_all_locks)]

    async def parse_lock(self, access_type: str, default: typing.Optional[str] = None):
        lock = self.locks.get(access_type, default)
        if not lock:
            return None
        if lock not in PARSER_CACHE:
            try:
                PARSER_CACHE[lock] = mudforge.LOCKPARSER.parse(lock)
            except LarkError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid lock: {e}"
                )
        return PARSER_CACHE[lock]

    async def check(self, accessor: "ActingAs", access_type: str) -> bool:
        lock = await self.parse_lock(access_type)
        if lock:
            return await self.evaluate_lock(accessor, access_type, lock)
        return False

    async def check_override(self, accessor: "ActingAs", access_type: str) -> bool:
        """
        Useful for specific case checks.
        """
        return False

    async def access(self, accessor: "ActingAs", access_type: str):
        if accessor.admin_level >= 4:
            return True
        if await self.check_override(accessor, access_type):
            return True
        return await self.check(accessor, access_type)

    async def evaluate_lock(
        self, accessor: "ActingAs", access_type: str, lock_parsed: lark.Tree
    ) -> bool:
        """
        Evaluate the parsed lock expression asynchronously.
        Lock expressions support:
         - Logical 'or' and 'and'
         - Unary '!' for negation
         - Function calls with comma-separated arguments.
        Each function call is looked up in mudforge.LOCKFUNCS and called with a LockArguments instance.
        """

        async def eval_node(node) -> bool:
            # If node is a token, we expect it to be a literal "true" or "false".
            if isinstance(node, lark.Token):
                # You might also support numeric literals here if needed.
                token_val = node.value.lower()
                if token_val in ("true", "false"):
                    return token_val == "true"
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unexpected token value in lock expression: {node.value}",
                )

            # If node is a Tree, check its data field.
            elif isinstance(node, lark.Tree):
                if node.data == "or_expr":
                    # Evaluate all children; return True if any is True.
                    for child in node.children:
                        if await eval_node(child):
                            return True
                    return False

                elif node.data == "and_expr":
                    # Evaluate all children; if any is False, the result is False.
                    for child in node.children:
                        if not await eval_node(child):
                            return False
                    return True

                elif node.data == "not_expr":
                    # Expect exactly one child.
                    if len(node.children) != 1:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Invalid not-expression in lock.",
                        )
                    return not await eval_node(node.children[0])

                elif node.data == "function_call":
                    # Assume the first child is the function name (a Token)
                    # and the second (optional) is an argument list.
                    func_name = node.children[0].value
                    args = []
                    if len(node.children) > 1:
                        arg_list = node.children[1]
                        # Here we assume arg_list is a Tree whose children are argument tokens.
                        for arg in arg_list.children:
                            # For simplicity, treat numeric tokens as ints (or floats if needed) and strings without quotes.
                            if arg.type in ("SIGNED_NUMBER", "NUMBER"):
                                try:
                                    args.append(int(arg.value))
                                except ValueError:
                                    args.append(float(arg.value))
                            elif arg.type == "ESCAPED_STRING":
                                # Remove surrounding quotes
                                args.append(arg.value[1:-1])
                            else:
                                args.append(arg.value)
                    # Create LockArguments using self.owner (the lock-holder), accessor, access_type, and the arguments.
                    lock_args = LockArguments(
                        object=self,
                        subject=accessor,
                        access_type=access_type,
                        args=args,
                    )
                    # Look up the lock function.
                    lockfunc = mudforge.LOCKFUNCS.get(func_name)
                    if lockfunc is None:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Unknown lock function: {func_name}",
                        )
                    # Call the lock function and await its result.
                    result = await lockfunc(lock_args)
                    if not isinstance(result, bool):
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Lock function '{func_name}' did not return a boolean.",
                        )
                    return result

                elif node.data in ("true_literal", "false_literal"):
                    # If your grammar defines explicit boolean literals.
                    return node.children[0].lower() == "true"

                else:
                    # For any other node, try evaluating its children and combining them.
                    # This is a fallback; ideally your grammar should cover all cases.
                    results = [await eval_node(child) for child in node.children]
                    # For simplicity, return True if all children evaluate to True.
                    return all(results)
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid node type in lock expression.",
                )

        # Start evaluation at the root of the parsed tree.
        return await eval_node(lock_parsed)
