import socket
import logging
import signal


class Server:
    def __init__(self, port, listen_backlog):
        # Initialize server socket
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.bind(('', port))
        self._server_socket.listen(listen_backlog)
        signal.signal(signal.SIGTERM, self.__handle_signal)
        self.running = True

    def __handle_signal(self, signum, frame):
        logging.info(f'action: signal_received | result: success | signal: {signum}')
        self.running = False
        self._server_socket.close()

    def run(self):
        """
        Dummy Server loop

        Server that accept a new connections and establishes a
        communication with a client. After client with communucation
        finishes, servers starts to accept new connections again
        """

        while self.running:
            try:
                client_sock = self.__accept_new_connection()
                if client_sock:
                    self.__handle_client_connection(client_sock)
            except OSError:
                if not self.running:
                    logging.info('action: accept_connections | result: success')
                else:
                    logging.error('action: accept_connections | result: fail | error: socket_closed')
                break

        self.__shutdown()

    def __shutdown(self):
        """Cierre graceful de recursos con logs específicos"""
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
            logging.error(f"action: receive_message | result: fail | error: {e}")
        finally:
            client_sock.close()

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
