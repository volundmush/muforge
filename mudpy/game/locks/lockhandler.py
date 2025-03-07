import typing
import lark
from dataclasses import dataclass
from lark.exceptions import LarkError
from fastapi import HTTPException, status

PARSER_CACHE = dict()


@dataclass(slots=True)
class LockArguments:
    object: typing.Any
    subject: "ActingAs"
    access_type: str
    args: typing.List[str | int]


class LockHandler:
    """
    This is the base lockhandler used for generic lock checks. It should be specialized for
    different types of lock-holders or users if needed.
    """

    async def set_lock(self, access_type: str, lock: str):
        try:
            parsed = mudpy.LOCKPARSER.parse(lock)
            PARSER_CACHE[lock] = parsed
        except LarkError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid lock: {e}"
            )
        self.lock_data[access_type] = lock

    async def parse_lock(self, access_type: str, default: typing.Optional[str] = None):
        lock = self.lock_data.get(access_type, default)
        if not lock:
            return None
        if lock not in PARSER_CACHE:
            try:
                PARSER_CACHE[lock] = mudpy.LOCKPARSER.parse(lock)
            except LarkError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid lock: {e}"
                )
        return PARSER_CACHE[lock]

    async def access(
        self,
        accessor: "ActingAs",
        access_type: str,
        default: typing.Optional[str] = None,
    ):
        if accessor.admin_level >= 4:
            return True
        lock = await self.parse_lock(access_type, default)
        if lock:
            return await self.evaluate_lock(accessor, access_type, lock)
        return False

    async def evaluate_lock(
        self, accessor: "ActingAs", access_type: str, lock_parsed: lark.Tree
    ) -> bool:
        """
        Evaluate the parsed lock expression asynchronously.
        Lock expressions support:
         - Logical 'or' and 'and'
         - Unary '!' for negation
         - Function calls with comma-separated arguments.
        Each function call is looked up in mudpy.LOCKFUNCS and called with a LockArguments instance.
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
                    lockfunc = mudpy.LOCKFUNCS.get(func_name)
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
