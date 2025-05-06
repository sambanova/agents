from e2b_code_interpreter import Sandbox


def sandbox_code(code: str) -> str:
    """
    sandbox to run python code.

    :param code: str

    returns:
        str: output of the code
    """

    sbx = Sandbox()

    result = sbx.run_code(code)
    if result.error:
        return result.error
    return result.logs.stdout