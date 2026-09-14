"""Run inside the API container to verify bundled gateway protocol support."""

import asyncio

from app.core.config import settings
from app.services.guacd_protocol import InstructionReader, encode_instruction


async def main():
    for protocol, required in {
        "vnc": {"hostname", "port", "password"},
        "rdp": {"hostname", "security", "ignore-cert", "cert-fingerprints"},
        "ssh": {"hostname", "host-key", "username", "password"},
    }.items():
        async with asyncio.timeout(10):
            reader, writer = await asyncio.open_connection(
                settings.guacd_host, settings.guacd_port
            )
            try:
                writer.write(encode_instruction("select", protocol).encode())
                await writer.drain()
                response = await InstructionReader(reader).read()
                if response[0] != "args" or not required.issubset(response[1:]):
                    raise RuntimeError(
                        f"Guacamole {protocol} lacks required protocol/security support"
                    )
                print(
                    f"Guacamole {protocol}: protocol and security parameters verified"
                )
            finally:
                writer.close()
                await writer.wait_closed()


asyncio.run(main())
