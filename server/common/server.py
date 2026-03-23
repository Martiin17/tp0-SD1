import socket
import logging
import signal
import os

from common.protocol import (
    recv_batch, send_batch_ack,
    send_winners,
    MSG_BATCH, MSG_DONE,
)
from common.utils import Bet, store_bets, load_bets, has_won, STORAGE_FILEPATH

TOTAL_AGENCIES = 5

class Server:
    def __init__(self, port, listen_backlog):
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind(("", port))
        self._server_socket.listen(listen_backlog)
        self.running = True
        signal.signal(signal.SIGTERM, self.__handle_signal)

    def __handle_signal(self, signum, frame):
        logging.info(f"action: signal_received | result: success | signal: {signum}")
        self.running = False
        self._server_socket.close()

    def run(self):

        if os.path.exists(STORAGE_FILEPATH):
            os.remove(STORAGE_FILEPATH)
            logging.info("action: cleanup_storage | result: success")

        agency_sockets: dict[str, socket.socket] = {}

        while self.running and len(agency_sockets) < TOTAL_AGENCIES:
            try:
                client_sock = self.__accept_new_connection()
                if client_sock:
                    self.__handle_bets(client_sock, agency_sockets)
            except Exception as e:
                if not self.running:
                    break
                logging.error(f"action: accept_connections | result: fail | error: {e}")

        if self.running and len(agency_sockets) == TOTAL_AGENCIES:
            self.__run_lottery(agency_sockets)

        self.__shutdown()

    def __handle_bets(self, client_sock: socket.socket, agency_sockets: dict):
        try:
            while True:
                msg_type, agency, records = recv_batch(client_sock)

                if msg_type == MSG_DONE:
                    logging.info(
                        f"action: done_received | result: success | agency: {agency}"
                    )

                    agency_sockets[agency] = client_sock
                    return

                try:
                    bets = []
                    for fn, ln, doc, birth, num in records:
                        bets.append(Bet(agency, fn, ln, doc, birth, num))
                        logging.info(f"action: apuesta_almacenada | result: success | dni: {doc} | numero: {num}")
                    
                    store_bets(bets)
                    send_batch_ack(client_sock, len(records), success=True)
                except Exception as e:
                    logging.error(f"action: apuesta_recibida | result: fail | error: {e}")
                    send_batch_ack(client_sock, len(records), success=False)
        except (OSError, ValueError) as e:
            logging.error(f"action: handle_bets | result: fail | error: {e}")
            client_sock.close()

    def __run_lottery(self, agency_sockets: dict[str, socket.socket]):
        logging.info("action: sorteo | result: success")

        winners_by_agency: dict[str, list[str]] = {str(i): [] for i in range(1, TOTAL_AGENCIES + 1)}
        
        try:
            for bet in load_bets():
                if has_won(bet):
                    winners_by_agency[str(bet.agency)].append(bet.document)
        except Exception as e:
            logging.error(f"action: load_bets | result: fail | error: {e}")

        for agency, sock in agency_sockets.items():
            try:
                send_winners(sock, winners_by_agency.get(agency, []))
                sock.shutdown(socket.SHUT_WR)
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