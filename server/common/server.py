import socket
import select
import logging
import signal
from typing import Optional

from common.protocol import (
    recv_batch, send_batch_ack,
    send_winners,
    MSG_BATCH, MSG_DONE,
)
from common.utils import Bet, store_bets, load_bets, has_won

TOTAL_AGENCIES = 5


class Server:
    def __init__(self, port, listen_backlog):
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.bind(("", port))
        self._server_socket.listen(listen_backlog)
        self.running = True
        signal.signal(signal.SIGTERM, self.__handle_signal)

    def __handle_signal(self, signum, frame):
        logging.info(f"action: signal_received | result: success | signal: {signum}")
        self.running = False
        self._server_socket.close()

    def run(self):
        """
        Phase 1: accept all TOTAL_AGENCIES connections.
        Phase 2: use select() to process one message at a time from each
                 agency socket, without blocking on any single one.
        Phase 3: run lottery and send winners once all agencies sent DONE.
        """
        agency_sockets: dict[str, socket.socket] = {}
        sock_to_agency: dict[socket.socket, Optional[str]] = {}

        pending_socks: list[socket.socket] = []
        while self.running and len(pending_socks) < TOTAL_AGENCIES:
            try:
                client_sock = self.__accept_new_connection()
                if client_sock:
                    pending_socks.append(client_sock)
                    sock_to_agency[client_sock] = None
            except OSError:
                if not self.running:
                    logging.info("action: accept_connections | result: success | info: server_stopped")
                else:
                    logging.error("action: accept_connections | result: fail | error: unexpected_socket_error")
                self.__shutdown()
                return

        if len(pending_socks) < TOTAL_AGENCIES:
            self.__shutdown()
            return

        done_agencies: set[str] = set()
        active_socks = list(pending_socks)

        while len(done_agencies) < TOTAL_AGENCIES and active_socks:
            readable, _, _ = select.select(active_socks, [], [], 30.0)
            if not readable:
                logging.error("action: sorteo | result: fail | error: timeout waiting for agencies")
                break

            for sock in readable:
                try:
                    msg_type, agency, records = recv_batch(sock)
                except OSError as e:
                    logging.error(f"action: recv_batch | result: fail | error: {e}")
                    active_socks.remove(sock)
                    sock.close()
                    continue

                if sock_to_agency[sock] is None:
                    sock_to_agency[sock] = agency
                    agency_sockets[agency] = sock

                if msg_type == MSG_DONE:
                    logging.info(f"action: done_received | result: success | agency: {agency}")
                    done_agencies.add(agency)
                    active_socks.remove(sock)
                    continue

                cantidad = len(records)
                try:
                    bets = [
                        Bet(agency, fn, ln, doc, birth, num)
                        for fn, ln, doc, birth, num in records
                    ]
                    store_bets(bets)
                    logging.info(
                        f"action: apuesta_recibida | result: success | cantidad: {cantidad}"
                    )
                    send_batch_ack(sock, cantidad, success=True)
                except Exception as e:
                    logging.error(
                        f"action: apuesta_recibida | result: fail | cantidad: {cantidad} | error: {e}"
                    )
                    send_batch_ack(sock, cantidad, success=False)

        if len(done_agencies) == TOTAL_AGENCIES:
            self.__run_lottery(agency_sockets)

        self.__shutdown()

    def __run_lottery(self, agency_sockets: dict):
        logging.info("action: sorteo | result: success")

        winners_by_agency: dict[str, list[str]] = {a: [] for a in agency_sockets}
        for bet in load_bets():
            key = str(bet.agency)
            if has_won(bet) and key in winners_by_agency:
                winners_by_agency[key].append(bet.document)

        for agency, sock in agency_sockets.items():
            try:
                send_winners(sock, winners_by_agency.get(agency, []))
            except OSError as e:
                logging.error(
                    f"action: send_winners | result: fail | agency: {agency} | error: {e}"
                )
            finally:
                sock.close()

    def __shutdown(self):
        logging.info("action: shutdown | result: in_progress | resource: server_socket")
        try:
            self._server_socket.close()
        except OSError:
            pass
        logging.info("action: shutdown | result: success")

    def __accept_new_connection(self):
        if not self.running:
            return None
        logging.info("action: accept_connections | result: in_progress")
        try:
            client_sock, addr = self._server_socket.accept()
            logging.info(f"action: accept_connections | result: success | ip: {addr[0]}")
            return client_sock
        except OSError:
            return None