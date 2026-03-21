package common

import (
	"net"
	"os"
	"time"

	"github.com/op/go-logging"
)

var log = logging.MustGetLogger("log")

type BetData struct {
	FirstName string
	LastName  string
	Document  string
	Birthdate string
	Number    string
}

// ClientConfig Configuration used by the client
type ClientConfig struct {
	ID            string
	ServerAddress string
	LoopPeriod    time.Duration
	Bet           BetData
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

		log.Infof("action: connect | result: in_progress  | client_id: %v | error: %v",
			c.config.ID, err)

		select {
		case <-time.After(c.config.LoopPeriod):
		case <-c.stop:
			c.handleShutdown()
			return
		}
	}

	defer c.conn.Close()

	bet := c.config.Bet
	if err := SendBet(c.conn, c.config.ID,
		bet.FirstName, bet.LastName, bet.Document, bet.Birthdate, bet.Number); err != nil {
		log.Errorf("action: send_bet | result: fail | client_id: %v | error: %v",
			c.config.ID, err)
		return
	}

	document, number, err := RecvAck(c.conn)
	if err != nil {
		log.Errorf("action: receive_message | result: fail | client_id: %v | error: %v",
			c.config.ID, err)
		return
	}

	log.Infof("action: apuesta_enviada | result: success | dni: %v | numero: %v",
		document, number)
}

func (c *Client) handleShutdown() {
	log.Infof("action: shutdown | result: in_progress | client_id: %v", c.config.ID)
	if c.conn != nil {
		c.conn.Close()
	}
	log.Infof("action: shutdown | result: success | client_id: %v", c.config.ID)
}