package common

import (
	"encoding/binary"
	"fmt"
	"net"
	"strings"
)

const (
	msgTypeBet = "BET"
	msgTypeAck = "ACK"
	separator  = "|"
	headerSize = 4
)

func sendAll(conn net.Conn, data []byte) error {
	sent := 0
	for sent < len(data) {
		n, err := conn.Write(data[sent:])
		if err != nil {
			return fmt.Errorf("sendAll: %w", err)
		}
		sent += n
	}
	return nil
}

func recvAll(conn net.Conn, n int) ([]byte, error) {
	buf := make([]byte, n)
	received := 0
	for received < n {
		r, err := conn.Read(buf[received:])
		if err != nil {
			return nil, fmt.Errorf("recvAll: %w", err)
		}
		received += r
	}
	return buf, nil
}

func sendMessage(conn net.Conn, body string) error {
	data := []byte(body)
	header := make([]byte, headerSize)
	binary.BigEndian.PutUint32(header, uint32(len(data)))

	if err := sendAll(conn, header); err != nil {
		return err
	}
	return sendAll(conn, data)
}

func recvMessage(conn net.Conn) (string, error) {
	header, err := recvAll(conn, headerSize)
	if err != nil {
		return "", err
	}
	length := binary.BigEndian.Uint32(header)
	body, err := recvAll(conn, int(length))
	if err != nil {
		return "", err
	}
	return string(body), nil
}

func SendBet(conn net.Conn, agency, firstName, lastName, document, birthdate, number string) error {
	fields := []string{msgTypeBet, agency, firstName, lastName, document, birthdate, number}
	return sendMessage(conn, strings.Join(fields, separator))
}

func RecvAck(conn net.Conn) (document, number string, err error) {
	msg, err := recvMessage(conn)
	if err != nil {
		return "", "", err
	}
	parts := strings.Split(msg, separator)
	if len(parts) != 3 || parts[0] != msgTypeAck {
		return "", "", fmt.Errorf("unexpected message: %s", msg)
	}
	return parts[1], parts[2], nil
}