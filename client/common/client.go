package common

import (
	"net"
	"os"
	"time"
	"io"
	"encoding/csv"

	"github.com/op/go-logging"
)

var log = logging.MustGetLogger("log")

// ClientConfig Configuration used by the client
type ClientConfig struct {
	ID            string
	ServerAddress string
	LoopPeriod    time.Duration
	BatchMaxAmount int
	DataFilePath  string
}

type Client struct {
	config ClientConfig
	conn   net.Conn
	stop   chan os.Signal
}

// NewClient Initializes a new client receiving the configuration
// as a parameter
func NewClient(config ClientConfig, stop chan os.Signal) *Client {
	client := &Client{
		config: config,
		stop:   stop,
	}
	return client
}

// CreateClientSocket Initializes client socket. In case of
// failure, error is printed in stdout/stderr and exit 1
// is returned
func (c *Client) createClientSocket() error {
	conn, err := net.Dial("tcp", c.config.ServerAddress)
	if err != nil {
		return err
	}
	c.conn = conn
	return nil
}

// StartClientLoop Send messages to the client until some time threshold is met
func (c *Client) StartClientLoop() {
	select {
	case <-c.stop:
		c.handleShutdown()
		return
	default:
	}

	for {
		err := c.createClientSocket()
		if err == nil {
			break
		}
		log.Infof("action: connect | result: in_progress | client_id: %v | error: %v",
			c.config.ID, err)
		select {
		case <-time.After(c.config.LoopPeriod):
		case <-c.stop:
			c.handleShutdown()
			return
		}
	}
	defer c.conn.Close()

	file, err := os.Open(c.config.DataFilePath)
	if err != nil {
		log.Errorf("action: open_file | result: fail | client_id: %v | error: %v",
			c.config.ID, err)
		return
	}
	defer file.Close()

	reader := csv.NewReader(file)
	batchSize := c.config.BatchMaxAmount
	if batchSize <= 0 {
		batchSize = 50
	}

	for {
		select {
		case <-c.stop:
			c.handleShutdown()
			return
		default:
		}

		batch, done, err := readBatch(reader, batchSize)
		if err != nil {
			log.Errorf("action: read_batch | result: fail | client_id: %v | error: %v",
				c.config.ID, err)
			return
		}

		if len(batch) == 0 {
			break
		}

		if err := SendBatch(c.conn, c.config.ID, batch); err != nil {
			log.Errorf("action: send_batch | result: fail | client_id: %v | error: %v",
				c.config.ID, err)
			return
		}

		cantidad, success, err := RecvBatchAck(c.conn)
		if err != nil {
			log.Errorf("action: receive_ack | result: fail | client_id: %v | error: %v",
				c.config.ID, err)
			return
		}

		if !success {
			log.Errorf("action: apuesta_enviada | result: fail | client_id: %v | cantidad: %v",
				c.config.ID, cantidad)
			return
		}

		log.Infof("action: apuesta_enviada | result: success | client_id: %v | cantidad: %v",
			c.config.ID, cantidad)

		if done {
			break
		}
	}

	if err := SendDone(c.conn, c.config.ID); err != nil {
		log.Errorf("action: send_done | result: fail | client_id: %v | error: %v",
			c.config.ID, err)
		return
	}

	winners, err := RecvWinners(c.conn)
	if err != nil {
		log.Errorf("action: consulta_ganadores | result: fail | client_id: %v | error: %v",
			c.config.ID, err)
		return
	}

	log.Infof("action: consulta_ganadores | result: success | cant_ganadores: %v",
		len(winners))

	log.Infof("action: loop_finished | result: success | client_id: %v", c.config.ID)
}

func readBatch(reader *csv.Reader, maxSize int) ([]BetRecord, bool, error) {
	var batch []BetRecord
	for i := 0; i < maxSize; i++ {
		row, err := reader.Read()
		if err == io.EOF {
			return batch, true, nil
		}
		if err != nil {
			return nil, false, err
		}
		if len(row) < 5 {
			continue
		}
		batch = append(batch, BetRecord{
			FirstName: row[0],
			LastName:  row[1],
			Document:  row[2],
			Birthdate: row[3],
			Number:    row[4],
		})
	}
	return batch, false, nil
}

func (c *Client) handleShutdown() {
	log.Infof("action: shutdown | result: in_progress | client_id: %v", c.config.ID)
	if c.conn != nil {
		c.conn.Close()
	}
	log.Infof("action: shutdown | result: success | client_id: %v", c.config.ID)
}