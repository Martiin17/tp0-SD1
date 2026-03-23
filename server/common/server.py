import socket
import select
import logging
import signal
import threading
from typing import Optional

from common.protocol import (
    recv_batch, send_batch_ack,
    send_winners,
    MSG_BATCH, MSG_DONE,
)
from common.utils import Bet, store_bets, load_bets, has_won

class Server:
    def __init__(self, port, listen_backlog, total_agencies=5):
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.bind(("", port))
        self._server_socket.listen(listen_backlog)
        self.running = True
        self._total_agencies = total_agencies
        self._store_lock = threading.Lock()
        self._lottery_barrier = threading.Barrier(total_agencies)
        self._winners: dict[str, list[str]] = {}
        signal.signal(signal.SIGTERM, self.__handle_signal)

    def __handle_signal(self, signum, frame):
        logging.info(f"action: signal_received | result: success | signal: {signum}")
        self.running = False
        self._server_socket.close()

    def run(self):
        threads = []

        while self.running and len(threads) < self._total_agencies:
            try:
                client_sock = self.__accept_new_connection()
                if client_sock:
                    t = threading.Thread(
                        target=self.__handle_agency,
                        args=(client_sock,),
                        daemon=True,
                    )
                    t.start()
                    threads.append(t)
            except OSError:
                if not self.running:
                    logging.info("action: accept_connections | result: success | info: server_stopped")
                else:
                    logging.error("action: accept_connections | result: fail | error: unexpected_socket_error")
                break

        for t in threads:
            t.join()

        self.__shutdown()

    def __handle_agency(self, client_sock: socket.socket):
        agency: Optional[str] = None
        try:
            while True:
                msg_type, agency, records = recv_batch(client_sock)

                if msg_type == MSG_DONE:
                    logging.info(
                        f"action: done_received | result: success | agency: {agency}"
                    )
                    break

                cantidad = len(records)
                try:
                    bets = [
                        Bet(agency, fn, ln, doc, birth, num)
                        for fn, ln, doc, birth, num in records
                    ]
                    with self._store_lock:
                        store_bets(bets)
                    logging.info(
                        f"action: apuesta_recibida | result: success | cantidad: {cantidad}"
                    )
                    send_batch_ack(client_sock, cantidad, success=True)
                except Exception as e:
                    logging.error(
                        f"action: apuesta_recibida | result: fail | cantidad: {cantidad} | error: {e}"
                    )
                    send_batch_ack(client_sock, cantidad, success=False)

            arrival_index = self._lottery_barrier.wait()

            if arrival_index == 0:
                self.__run_lottery()
            self._lottery_barrier.wait()
            winners = self._winners.get(agency, [])
            send_winners(client_sock, winners)

        except OSError as e:
            logging.error(
                f"action: handle_agency | result: fail | agency: {agency} | error: {e}"
            )
        finally:
            client_sock.close()

    def __run_lottery(self):
        logging.info("action: sorteo | result: success")
        winners: dict[str, list[str]] = {}
        for bet in load_bets():
            key = str(bet.agency)
            if has_won(bet):
                winners.setdefault(key, []).append(bet.document)
        self._winners = winners

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
            logging.info(
                f"action: accept_connections | result: success | ip: {addr[0]}"
            )
            return client_sock
        except OSError:
            return None