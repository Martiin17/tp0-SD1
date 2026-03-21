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

// InitConfig Function that uses viper library to parse configuration parameters.
// Viper is configured to read variables from both environment variables and the
// config file ./config.yaml. Environment variables takes precedence over parameters
// defined in the configuration file. If some of the variables cannot be parsed,
// an error is returned
func InitConfig() (*viper.Viper, error) {
	v := viper.New()

	v.AutomaticEnv()
	v.SetEnvPrefix("cli")
	v.SetEnvKeyReplacer(strings.NewReplacer(".", "_"))

	v.BindEnv("id")
	v.BindEnv("server.address")
	v.BindEnv("loop.period")
	v.BindEnv("log.level")

	v.BindEnv("nombre", "NOMBRE")
	v.BindEnv("apellido", "APELLIDO")
	v.BindEnv("documento", "DOCUMENTO")
	v.BindEnv("nacimiento", "NACIMIENTO")
	v.BindEnv("numero", "NUMERO")

	v.SetConfigFile("./config.yaml")
	if err := v.ReadInConfig(); err != nil {
		fmt.Printf("Configuration could not be read from config file. Using env variables instead\n")
	}

	if _, err := time.ParseDuration(v.GetString("loop.period")); err != nil {
		return nil, errors.Wrapf(err, "Could not parse CLI_LOOP_PERIOD env var as time.Duration.")
	}

	return v, nil
}

func readBetFromViper(v *viper.Viper) (common.BetData, error) {
	fields := map[string]string{
		"nombre":    v.GetString("nombre"),
		"apellido":  v.GetString("apellido"),
		"documento": v.GetString("documento"),
		"nacimiento": v.GetString("nacimiento"),
		"numero":    v.GetString("numero"),
	}

	for key, val := range fields {
		if val == "" {
			return common.BetData{}, fmt.Errorf("missing required env variable: %s", strings.ToUpper(key))
		}
	}

	return common.BetData{
		FirstName: fields["nombre"],
		LastName:  fields["apellido"],
		Document:  fields["documento"],
		Birthdate: fields["nacimiento"],
		Number:    fields["numero"],
	}, nil
}

func PrintConfig(v *viper.Viper, bet common.BetData) {
	log.Infof("action: config | result: success | client_id: %s | server_address: %s | "+
		"nombre: %s | apellido: %s | documento: %s | nacimiento: %s | numero: %s",
		v.GetString("id"),
		v.GetString("server.address"),
		bet.FirstName,
		bet.LastName,
		bet.Document,
		bet.Birthdate,
		bet.Number,
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

	bet, err := readBetFromViper(v)
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