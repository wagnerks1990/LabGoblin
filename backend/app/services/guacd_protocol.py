"""Bounded Guacamole instruction framing (lengths count Unicode code points)."""

import codecs


def encode_instruction(*elements):
    values = [str(value) for value in elements]
    return ",".join(f"{len(value)}.{value}" for value in values) + ";"


class InstructionParser:
    def __init__(self, limit=1048576):
        self.buffer = ""
        self.limit = limit

    def feed(self, data):
        self.buffer += data
        if len(self.buffer) > self.limit:
            raise ValueError("Guacamole instruction exceeds limit")

    def pop(self):
        offset, elements = 0, []
        while True:
            dot = self.buffer.find(".", offset)
            if dot < 0:
                if len(self.buffer) - offset > 7:
                    raise ValueError("Invalid Guacamole length")
                return None
            length = self.buffer[offset:dot]
            if not length.isascii() or not length.isdigit() or len(length) > 7:
                raise ValueError("Invalid Guacamole length")
            count = int(length)
            if count > self.limit:
                raise ValueError("Guacamole element exceeds limit")
            end = dot + 1 + count
            if end >= len(self.buffer):
                return None
            elements.append(self.buffer[dot + 1 : end])
            if len(elements) > 256:
                raise ValueError("Too many Guacamole elements")
            separator = self.buffer[end]
            if separator == ";":
                self.buffer = self.buffer[end + 1 :]
                return elements
            if separator != ",":
                raise ValueError("Invalid Guacamole separator")
            offset = end + 1


class InstructionReader:
    def __init__(self, reader):
        self.reader = reader
        self.parser = InstructionParser()
        self.decoder = codecs.getincrementaldecoder("utf-8")("strict")

    async def read(self):
        while True:
            instruction = self.parser.pop()
            if instruction is not None:
                return instruction
            data = await self.reader.read(16384)
            if not data:
                raise EOFError("Guacamole tunnel closed")
            self.parser.feed(self.decoder.decode(data))


def validate_browser_instruction(elements):
    # No select/connect/argv/join or host/credential changes from the browser.
    # No clipboard, filesystem, SFTP, printing, drive or audio input streams.
    opcode, *args = elements
    if opcode == "disconnect" and not args:
        return False
    if opcode == "nop" and not args:
        return True
    if opcode == "sync" and len(args) == 1 and args[0].isdigit():
        return True
    if (
        opcode == "ack"
        and len(args) == 3
        and args[0].isdigit()
        and args[2].isdigit()
        and len(args[1]) <= 256
    ):
        return True
    if (
        opcode == "key"
        and len(args) == 2
        and args[0].isdigit()
        and 0 <= int(args[0]) <= 0xFFFFFFFF
        and args[1] in {"0", "1"}
    ):
        return True
    if (
        opcode == "mouse"
        and len(args) in {3, 4}
        and all(value.isdigit() for value in args)
    ):
        if int(args[0]) <= 8192 and int(args[1]) <= 8192 and int(args[2]) <= 31:
            return True
    if opcode == "size" and len(args) == 2 and all(value.isdigit() for value in args):
        if all(200 <= int(value) <= 4096 for value in args):
            return True
    raise ValueError("Unsupported browser instruction")


async def handshake(reader, writer, protocol, parameters, width, height):
    def send(*values):
        writer.write(encode_instruction(*values).encode())

    send("select", protocol)
    await writer.drain()
    instruction = await reader.read()
    if instruction[0] != "args":
        raise ValueError("Gateway rejected protocol")
    arguments = instruction[1:]
    required = {"hostname", "port"}
    if protocol == "rdp":
        required |= {
            "security",
            "ignore-cert",
            "cert-fingerprints",
            "username",
            "password",
        }
    if protocol == "ssh":
        required |= {"host-key", "username", "password"}
    if not required.issubset(arguments):
        raise ValueError("Gateway lacks required security parameters")
    send("size", width, height, 96)
    send("audio")
    send("video")
    send("image", "image/png", "image/jpeg")
    values = [
        "VERSION_1_5_0" if arg.startswith("VERSION_") else parameters.get(arg, "")
        for arg in arguments
    ]
    send("connect", *values)
    await writer.drain()
    instruction = await reader.read()
    if instruction[0] != "ready":
        raise ValueError("Gateway connection failed")
