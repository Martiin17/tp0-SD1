import socket
import struct

SEPARATOR = "|"
RECORD_SEP = "\n"
HEADER_SIZE = 4 

MSG_BET       = "BET"
MSG_ACK       = "ACK"
MSG_BATCH     = "BATCH"
MSG_BATCH_OK  = "BATCH_OK"
MSG_BATCH_ERR = "BATCH_ERR"
MSG_DONE      = "DONE"
MSG_WINNERS   = "WINNERS"


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
    """Send a length-prefixed message."""
    data = body.encode("utf-8")
    _send_all(sock, struct.pack("!I", len(data)))
    _send_all(sock, data)


def recv_message(sock: socket.socket) -> str:
    """Receive a length-prefixed message."""
    length = struct.unpack("!I", _recv_all(sock, HEADER_SIZE))[0]
    return _recv_all(sock, length).decode("utf-8")


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
    send_message(sock, SEPARATOR.join([MSG_ACK, document, number]))


def recv_batch(sock: socket.socket) -> tuple[str, list[tuple]]:
    msg = recv_message(sock)
    lines = msg.split(RECORD_SEP)
    header_parts = lines[0].split(SEPARATOR)

    if header_parts[0] == MSG_DONE:
        if len(header_parts) != 2:
            raise ValueError(f"Invalid DONE message: {lines[0]!r}")
        return MSG_DONE, header_parts[1], []

    if header_parts[0] != MSG_BATCH or len(header_parts) != 3:
        raise ValueError(f"Invalid BATCH header: {lines[0]!r}")

    agency = header_parts[1]
    n_bets = int(header_parts[2])
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

    return MSG_BATCH, agency, records


def send_batch_ack(sock: socket.socket, cantidad: int, success: bool) -> None:
    msg_type = MSG_BATCH_OK if success else MSG_BATCH_ERR
    send_message(sock, SEPARATOR.join([msg_type, str(cantidad)]))


def send_done(sock: socket.socket, agency: str) -> None:
    send_message(sock, SEPARATOR.join([MSG_DONE, agency]))


def send_winners(sock: socket.socket, documents: list[str]) -> None:
    lines = [f"{MSG_WINNERS}{SEPARATOR}{len(documents)}"]
    lines.extend(documents)
    send_message(sock, RECORD_SEP.join(lines))


def recv_winners(sock: socket.socket) -> list[str]:
    msg = recv_message(sock)
    lines = msg.split(RECORD_SEP)
    header_parts = lines[0].split(SEPARATOR)
    if len(header_parts) != 2 or header_parts[0] != MSG_WINNERS:
        raise ValueError(f"Invalid WINNERS message: {lines[0]!r}")
    n = int(header_parts[1])
    documents = [l for l in lines[1:] if l]
    if len(documents) != n:
        raise ValueError(f"Expected {n} winners, got {len(documents)}")
    return documents