package common

import (
	"bufio"
	"fmt"
	"net"
	"os"
	"time"

	"github.com/op/go-logging"
)

var log = logging.MustGetLogger("log")

// ClientConfig Configuration used by the client
type ClientConfig struct {
	ID            string
	ServerAddress string
	LoopAmount    int
	LoopPeriod    time.Duration
}

// Client Entity that encapsulates how
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

func sendAll(conn net.Conn, data []byte) error {
    sent := 0
    for sent < len(data) {
        n, err := conn.Write(data[sent:])
        if err != nil {
            return err
        }
        sent += n
    }
    return nil
}

// StartClientLoop Send messages to the client until some time threshold is met
func (c *Client) StartClientLoop() {
	// There is an autoincremental msgID to identify every message sent
	// Messages if the message amount threshold has not been surpassed
	for msgID := 1; msgID <= c.config.LoopAmount; msgID++ {
		
		select {
			case <-c.stop:
				c.handleShutdown()
				return
			default:
		}

		err := c.createClientSocket()
		if err != nil {
			log.Errorf(
				"action: connect | result: in_progress | client_id: %v",
				c.config.ID,
			)

			select {
			case <-time.After(c.config.LoopPeriod):
				msgID--
				continue
			case <-c.stop:
				c.handleShutdown()
				return
			}
		}

		msg := fmt.Sprintf("[CLIENT %v] Message N°%v\n", c.config.ID, msgID)
		if err := sendAll(c.conn, []byte(msg)); err != nil {
			log.Errorf("action: send_message | result: fail | client_id: %v | error: %v",
				c.config.ID, err)
			c.conn.Close()
			return
		}

		msg, err := bufio.NewReader(c.conn).ReadString('\n')
		c.conn.Close()

		if err != nil {
			log.Errorf("action: receive_message | result: fail | client_id: %v | error: %v",
				c.config.ID,
				err,
			)
			return
		}

		log.Infof("action: receive_message | result: success | client_id: %v | msg: %v",
			c.config.ID,
			msg,
		)

		select {
			case <-time.After(c.config.LoopPeriod):
			case <-c.stop:
				c.handleShutdown()
				return
		}
	}

	log.Infof("action: loop_finished | result: success | client_id: %v", c.config.ID)
}

func (c *Client) handleShutdown() {
	log.Infof("action: shutdown | result: in_progress | client_id: %v | resource: main_loop", c.config.ID)
    if c.conn != nil {
        c.conn.Close()
    }
    log.Infof("action: shutdown | result: success | client_id: %v", c.config.ID)
}