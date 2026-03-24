import socket
import logging
import signal


class Server:
    def __init__(self, port, listen_backlog):
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind(('', port))
        self._server_socket.listen(listen_backlog)
        self.running = True
        self._client_sock = None
        signal.signal(signal.SIGTERM, self.__handle_signal)

    def __handle_signal(self, signum, frame):
        logging.info(f'action: signal_received | result: success | signal: {signum}')
        self.running = False
        if self._client_sock:
            try:
                self._client_sock.close()
            except:
                pass
        try:
            self._server_socket.close()
        except:
            pass

    def run(self):
        while self.running:
            try:
                client_sock = self.__accept_new_connection()
                if client_sock is None:
                    break
                self._client_sock = client_sock
                self.__handle_client_connection(client_sock)
                self._client_sock = None
            except OSError:
                if not self.running:
                    break
                logging.error('action: accept_connections | result: fail | error: socket_closed')
                break

        self.__shutdown()

    def __shutdown(self):
        logging.info('action: shutdown | result: in_progress | resource: server_socket')
        try:
            self._server_socket.close()
        except:
            pass
        logging.info('action: shutdown | result: success')

    def __accept_new_connection(self):
        if not self.running:
            return None
        try:
            c, addr = self._server_socket.accept()
            logging.info(f'action: accept_connections | result: success | ip: {addr[0]}')
            return c
        except OSError:
            return None

    def __handle_client_connection(self, client_sock):
        try:
            msg = self.__recv_line(client_sock)
            addr = client_sock.getpeername()
            logging.info(f'action: receive_message | result: success | ip: {addr[0]} | msg: {msg}')
            self.__send_all(client_sock, f"{msg}\n".encode('utf-8'))
        except OSError as e:
            if self.running:
                logging.error(f"action: receive_message | result: fail | error: {e}")
        finally:
            try:
                client_sock.close()
                logging.info('action: client_connection | result: closed')
            except:
                pass

    def __recv_line(self, sock: socket.socket) -> str:
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = sock.recv(1)
            if not chunk:
                raise OSError("Connection closed while reading")
            buf += chunk
        return buf.rstrip().decode('utf-8')

    def __send_all(self, sock: socket.socket, data: bytes) -> None:
        sent = 0
        while sent < len(data):
            n = sock.send(data[sent:])
            if n == 0:
                raise OSError("Connection closed while sending")
            sent += n