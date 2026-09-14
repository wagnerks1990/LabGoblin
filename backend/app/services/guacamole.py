import asyncio

from app.core.config import settings
from app.services.guacd_protocol import InstructionReader, encode_instruction


def guacamole_configured() -> bool:
    return bool(settings.guacd_host and settings.guacd_port)


async def check_guacamole_reachable(timeout: float = 2.5) -> tuple[bool, str | None]:
    writer = None
    try:
        async with asyncio.timeout(timeout):
            reader, writer = await asyncio.open_connection(
                settings.guacd_host, settings.guacd_port
            )
            writer.write(encode_instruction("select", "vnc").encode())
            await writer.drain()
            instruction = await InstructionReader(reader).read()
            if instruction[0] == "args":
                return True, None
            return False, "Gateway did not accept VNC"
    except Exception:
        return False, "Private Guacamole gateway is unavailable"
    finally:
        if writer:
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass
