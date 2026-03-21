package common

import (
	"encoding/binary"
	"fmt"
	"net"
	"strconv"
	"strings"
)

const (
	msgTypeBet      = "BET"
	msgTypeAck      = "ACK"
	msgTypeBatch    = "BATCH"
	msgTypeBatchOK  = "BATCH_OK"
	msgTypeBatchErr = "BATCH_ERR"
	separator       = "|"
	recordSep       = "\n"
	headerSize      = 4
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

type BetRecord struct {
	FirstName string
	LastName  string
	Document  string
	Birthdate string
	Number    string
}

func SendBatch(conn net.Conn, agency string, bets []BetRecord) error {
	var sb strings.Builder
	sb.WriteString(msgTypeBatch)
	sb.WriteString(separator)
	sb.WriteString(agency)
	sb.WriteString(separator)
	sb.WriteString(strconv.Itoa(len(bets)))
	for _, b := range bets {
		sb.WriteString(recordSep)
		sb.WriteString(strings.Join([]string{b.FirstName, b.LastName, b.Document, b.Birthdate, b.Number}, separator))
	}
	return sendMessage(conn, sb.String())
}

func RecvBatchAck(conn net.Conn) (cantidad int, success bool, err error) {
	msg, err := recvMessage(conn)
	if err != nil {
		return 0, false, err
	}
	parts := strings.Split(msg, separator)
	if len(parts) != 2 {
		return 0, false, fmt.Errorf("unexpected batch ack: %s", msg)
	}
	cantidad, err = strconv.Atoi(parts[1])
	if err != nil {
		return 0, false, fmt.Errorf("invalid cantidad in ack: %s", msg)
	}
	switch parts[0] {
	case msgTypeBatchOK:
		return cantidad, true, nil
	case msgTypeBatchErr:
		return cantidad, false, nil
	default:
		return 0, false, fmt.Errorf("unknown ack type: %s", parts[0])
	}
}