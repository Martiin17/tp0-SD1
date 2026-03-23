import socket
import logging
import signal

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
        Accept connections from all agencies, process their bets,
        then run the lottery and return winners to each agency.
        """
        agency_sockets: dict[str, socket.socket] = {}

        while self.running and len(agency_sockets) < TOTAL_AGENCIES:
            try:
                client_sock = self.__accept_new_connection()
                if client_sock:
                    self.__handle_bets(client_sock, agency_sockets)
            except OSError:
                if not self.running:
                    logging.info("action: accept_connections | result: success | info: server_stopped")
                else:
                    logging.error("action: accept_connections | result: fail | error: unexpected_socket_error")
                break

        if len(agency_sockets) == TOTAL_AGENCIES:
            self.__run_lottery(agency_sockets)

        self.__shutdown()

    def __handle_bets(self, client_sock: socket.socket, agency_sockets: dict):
        """
        Receive all batches from one client until it sends DONE.
        Then store the socket to later send winners.
        """
        try:
            while True:
                msg_type, agency, records = recv_batch(client_sock)

                if msg_type == MSG_DONE:
                    logging.info(
                        f"action: done_received | result: success | agency: {agency}"
                    )

                    agency_sockets[agency] = client_sock
                    return

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
                    send_batch_ack(client_sock, cantidad, success=True)
                except Exception as e:
                    logging.error(
                        f"action: apuesta_recibida | result: fail | cantidad: {cantidad} | error: {e}"
                    )
                    send_batch_ack(client_sock, cantidad, success=False)

        except OSError as e:
            logging.error(f"action: handle_bets | result: fail | error: {e}")
            client_sock.close()

    def __run_lottery(self, agency_sockets: dict[str, socket.socket]):
        """
        Run the lottery once all 5 agencies have sent DONE.
        Send each agency its winners and close the sockets.
        """
        logging.info("action: sorteo | result: success")

        winners_by_agency: dict[str, list[str]] = {agency: [] for agency in agency_sockets}
        for bet in load_bets():
            agency_key = str(bet.agency)
            if has_won(bet) and agency_key in winners_by_agency:
                winners_by_agency[agency_key].append(bet.document)

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