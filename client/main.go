package main

import (
	"fmt"
	"os"
	"strings"
	"time"
	"os/signal"
	"syscall"

	"github.com/op/go-logging"
	"github.com/pkg/errors"
	"github.com/spf13/viper"
	"github.com/7574-sistemas-distribuidos/docker-compose-init/client/common"
)

var log = logging.MustGetLogger("log")

// InitConfig Function that uses viper library to parse configuration parameters.
// Viper is configured to read variables from both environment variables and the
// config file ./config.yaml. Environment variables takes precedence over parameters
// defined in the configuration file. If some of the variables cannot be parsed,
// an error is returned
func InitConfig() (*viper.Viper, error) {
	v := viper.New()

	// Configure viper to read env variables with the CLI_ prefix
	v.AutomaticEnv()
	v.SetEnvPrefix("cli")
	// Use a replacer to replace env variables underscores with points. This let us
	// use nested configurations in the config file and at the same time define
	// env variables for the nested configurations
	v.SetEnvKeyReplacer(strings.NewReplacer(".", "_"))

	v.BindEnv("id")
	v.BindEnv("server.address")
	v.BindEnv("loop.period")
	v.BindEnv("log.level")

	// Try to read configuration from config file. If config file
	// does not exists then ReadInConfig will fail but configuration
	// can be loaded from the environment variables so we shouldn't
	// return an error in that case
	v.SetConfigFile("./config.yaml")
	if err := v.ReadInConfig(); err != nil {
		fmt.Printf("Configuration could not be read from config file. Using env variables instead\n")
	}

	if _, err := time.ParseDuration(v.GetString("loop.period")); err != nil {
		return nil, errors.Wrapf(err, "Could not parse CLI_LOOP_PERIOD env var as time.Duration.")
	}

	return v, nil
}

// InitLogger Receives the log level to be set in go-logging as a string. This method
// parses the string and set the level to the logger. If the level string is not
// valid an error is returned
func InitLogger(logLevel string) error {
	baseBackend := logging.NewLogBackend(os.Stdout, "", 0)
	format := logging.MustStringFormatter(
		`%{time:2006-01-02 15:04:05} %{level:.5s}     %{message}`,
	)
	backendFormatter := logging.NewBackendFormatter(baseBackend, format)
	backendLeveled := logging.AddModuleLevel(backendFormatter)
	logLevelCode, err := logging.LogLevel(logLevel)
	if err != nil {
		return err
	}
	backendLeveled.SetLevel(logLevelCode, "")
	logging.SetBackend(backendLeveled)
	return nil
}

// readBetFromEnv reads the bet fields from environment variables.
// Expected vars: NOMBRE, APELLIDO, DOCUMENTO, NACIMIENTO, NUMERO
func readBetFromEnv() (common.BetData, error) {
	required := map[string]string{
		"NOMBRE":    "",
		"APELLIDO":  "",
		"DOCUMENTO": "",
		"NACIMIENTO": "",
		"NUMERO":    "",
	}

	for key := range required {
		val := os.Getenv(key)
		if val == "" {
			return common.BetData{}, fmt.Errorf("missing required env variable: %s", key)
		}
		required[key] = val
	}

	return common.BetData{
		FirstName: required["NOMBRE"],
		LastName:  required["APELLIDO"],
		Document:  required["DOCUMENTO"],
		Birthdate: required["NACIMIENTO"],
		Number:    required["NUMERO"],
	}, nil
}

func PrintConfig(v *viper.Viper, bet common.BetData) {
	log.Infof("action: config | result: success | client_id: %s | server_address: %s | "+
		"nombre: %s | apellido: %s | documento: %s | nacimiento: %s | numero: %s | log_level: %s",
		v.GetString("id"),
		v.GetString("server.address"),
		bet.FirstName,
		bet.LastName,
		bet.Document,
		bet.Birthdate,
		bet.Number,
		v.GetString("log.level"),
	)
}

func main() {
	v, err := InitConfig()
	if err != nil {
		log.Criticalf("%s", err)
		os.Exit(1)
	}

	if err := InitLogger(v.GetString("log.level")); err != nil {
		log.Criticalf("%s", err)
		os.Exit(1)
	}

	bet, err := readBetFromEnv()
	if err != nil {
		log.Criticalf("action: read_bet_env | result: fail | error: %v", err)
		os.Exit(1)
	}

	PrintConfig(v, bet)

	loopPeriod, _ := time.ParseDuration(v.GetString("loop.period"))

	sigs := make(chan os.Signal, 1)
	signal.Notify(sigs, syscall.SIGTERM)

	clientConfig := common.ClientConfig{
		ID:            v.GetString("id"),
		ServerAddress: v.GetString("server.address"),
		LoopPeriod:    loopPeriod,
		Bet:           bet,
	}

	client := common.NewClient(clientConfig, sigs)
	client.StartClientLoop()
}