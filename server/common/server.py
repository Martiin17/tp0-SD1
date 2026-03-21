import socket
import logging
import signal

from common.protocol import recv_batch, send_batch_ack, MSG_BATCH
from common.utils import Bet, store_bets


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
        while self.running:
            try:
                client_sock = self.__accept_new_connection()
                if client_sock:
                    self.__handle_client_connection(client_sock)
            except OSError:
                if not self.running:
                    logging.info("action: accept_connections | result: success | info: server_stopped")
                else:
                    logging.error("action: accept_connections | result: fail | error: unexpected_socket_error")
                break

        self.__shutdown()

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

    def __handle_client_connection(self, client_sock: socket.socket):
        try:
            while True:
                try:
                    agency, records = recv_batch(client_sock)
                except OSError:
                    break

                cantidad = len(records)
                try:
                    bets = [
                        Bet(agency, first_name, last_name, document, birthdate, number)
                        for first_name, last_name, document, birthdate, number in records
                    ]
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

        except Exception as e:
            logging.error(f"action: handle_client | result: fail | error: {e}")
        finally:
            client_sock.close()