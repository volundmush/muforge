from muforge.shared.utils import run_program, get_config

async def main(mode: str):
    settings = get_config(mode)
    await run_program(mode, settings)

def startup(mode: str):
    run = None
    try:
        from uvloop import run
    except ImportError:
        from asyncio import run
    run(main(mode), debug=True)
