import socket
import struct
import logging

SEPARATOR = "|"
RECORD_SEP = "\n"
HEADER_SIZE = 4 

MSG_BET       = "BET"
MSG_ACK       = "ACK"
MSG_BATCH     = "BATCH"
MSG_BATCH_OK  = "BATCH_OK"
MSG_BATCH_ERR = "BATCH_ERR"


def _send_all(sock: socket.socket, data: bytes) -> None:
    """Send all bytes in data, avoiding short-writes."""
    sent = 0
    while sent < len(data):
        n = sock.send(data[sent:])
        if n == 0:
            raise OSError("Connection closed while sending data")
        sent += n


def _recv_all(sock: socket.socket, n: int) -> bytes:
    """Receive exactly n bytes, avoiding short-reads."""
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise OSError("Connection closed while receiving data")
        buf += chunk
    return buf


def send_message(sock: socket.socket, body: str) -> None:
    """Send a length-prefixed message: [4-byte length][UTF-8 body]."""
    data = body.encode("utf-8")
    header = struct.pack("!I", len(data))
    _send_all(sock, header)
    _send_all(sock, data)


def recv_message(sock: socket.socket) -> str:
    """Receive a length-prefixed message and return its body as a string."""
    header = _recv_all(sock, HEADER_SIZE)
    length = struct.unpack("!I", header)[0]
    body = _recv_all(sock, length)
    return body.decode("utf-8")


def recv_bet_fields(sock: socket.socket) -> tuple:
    """
    Receive a BET message and return:
    (agency, first_name, last_name, document, birthdate, number)
    """
    msg = recv_message(sock)
    parts = msg.split(SEPARATOR)
    if len(parts) != 7 or parts[0] != MSG_BET:
        raise ValueError(f"Invalid BET message: {msg!r}")
    _, agency, first_name, last_name, document, birthdate, number = parts
    return agency, first_name, last_name, document, birthdate, number


def send_ack(sock: socket.socket, document: str, number: str) -> None:
    """Send an ACK confirming a single stored bet."""
    body = SEPARATOR.join([MSG_ACK, document, number])
    send_message(sock, body)


def recv_batch(sock: socket.socket) -> tuple[str, list[tuple]]:
    msg = recv_message(sock)
    lines = msg.split(RECORD_SEP)

    header_parts = lines[0].split(SEPARATOR)
    if len(header_parts) != 3 or header_parts[0] != MSG_BATCH:
        raise ValueError(f"Invalid BATCH header: {lines[0]!r}")

    agency  = header_parts[1]
    n_bets  = int(header_parts[2])
    records = []

    for line in lines[1:]:
        if not line:
            continue
        fields = line.split(SEPARATOR)
        if len(fields) != 5:
            raise ValueError(f"Invalid bet record: {line!r}")
        records.append(tuple(fields))

    if len(records) != n_bets:
        raise ValueError(f"Expected {n_bets} bets, got {len(records)}")

    return agency, records


def send_batch_ack(sock: socket.socket, cantidad: int, success: bool) -> None:
    msg_type = MSG_BATCH_OK if success else MSG_BATCH_ERR
    send_message(sock, SEPARATOR.join([msg_type, str(cantidad)]))